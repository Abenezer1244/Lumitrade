"""
Lumitrade Database Client
===========================
Async Supabase client wrapper. All queries parameterized.
Never uses raw SQL string interpolation.
Per SS Section 4.1.
"""

from __future__ import annotations

from typing import Any, Mapping, Union

from supabase import AsyncClient, create_async_client

from ..config import LumitradeConfig
from .secure_logger import get_logger

logger = get_logger(__name__)


# Recursive JSON value type used for filter / insert / update payloads.
# Postgres + Supabase accept any JSON-serializable scalar plus list/dict
# of the same. Using a recursive alias keeps the public method signatures
# honest without forcing callers to cast.
JsonValue = Union[
    None,
    bool,
    int,
    float,
    str,
    list["JsonValue"],
    dict[str, "JsonValue"],
]
JsonRow = Mapping[str, JsonValue]


class DatabaseClient:
    """All database operations go through this class. Parameterized only."""

    def __init__(self, config: LumitradeConfig):
        self.config = config
        self._client: AsyncClient | None = None

    async def connect(self) -> None:
        """Initialize async Supabase client."""
        self._client = await create_async_client(
            self.config.supabase_url,
            self.config.supabase_service_key,
        )
        logger.info("database_connected", url=self.config.supabase_url)

    @property
    def client(self) -> AsyncClient:
        if self._client is None:
            raise RuntimeError("DatabaseClient not connected. Call connect() first.")
        return self._client

    async def insert(self, table: str, data: JsonRow) -> list[dict[str, Any]]:
        """Parameterized insert — never raw SQL.

        Returns the list of inserted rows as returned by Supabase
        (``result.data``). Callers should treat the return value as
        opaque except for length / membership checks.
        """
        result = await self.client.table(table).insert(data).execute()
        return result.data

    async def select(
        self,
        table: str,
        filters: JsonRow,
        columns: str = "*",
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Parameterized select with filter dict."""
        query = self.client.table(table).select(columns)
        for key, value in filters.items():
            query = query.eq(key, value)
        if order:
            query = query.order(order, desc=True)
        if limit:
            query = query.limit(limit)
        result = await query.execute()
        return result.data

    async def select_one(self, table: str, filters: JsonRow) -> dict[str, Any] | None:
        """Select a single row matching filters."""
        rows = await self.select(table, filters, limit=1)
        return rows[0] if rows else None

    async def update(
        self, table: str, filters: JsonRow, data: JsonRow
    ) -> list[dict[str, Any]]:
        """Parameterized update."""
        query = self.client.table(table).update(data)
        for key, value in filters.items():
            query = query.eq(key, value)
        result = await query.execute()
        return result.data

    async def upsert(self, table: str, data: JsonRow) -> list[dict[str, Any]]:
        """Parameterized upsert."""
        result = await self.client.table(table).upsert(data).execute()
        return result.data

    async def count(self, table: str, filters: JsonRow) -> int:
        """Count rows matching filters."""
        query = self.client.table(table).select("*", count="exact")
        for key, value in filters.items():
            query = query.eq(key, value)
        result = await query.execute()
        return result.count or 0

    async def delete(self, table: str, filters: JsonRow) -> list[dict[str, Any]]:
        """Parameterized delete."""
        query = self.client.table(table).delete()
        for key, value in filters.items():
            query = query.eq(key, value)
        result = await query.execute()
        return result.data
