"""Track 4: Find deferred imports (imports inside function bodies).

These usually indicate a latent circular dependency that the author worked
around. Each one deserves a short rationale.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent / "lumitrade"


def find_deferred(path: Path) -> list[tuple[int, str, str]]:
    """Return (lineno, enclosing_func, import_text) for each in-function import."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    found: list[tuple[int, str, str]] = []

    class V(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def _enter(self, node, name: str) -> None:
            self.stack.append(name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._enter(node, node.name)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._enter(node, node.name)

        def visit_Import(self, node: ast.Import) -> None:
            if self.stack:
                for a in node.names:
                    if "lumitrade" in a.name:
                        found.append((node.lineno, ".".join(self.stack), f"import {a.name}"))

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if self.stack:
                mod = node.module or ""
                rel = "." * (node.level or 0)
                if (node.level or 0) > 0 or "lumitrade" in mod:
                    names = ", ".join(a.name for a in node.names)
                    found.append((node.lineno, ".".join(self.stack), f"from {rel}{mod} import {names}"))

    V().visit(tree)
    return found


def main() -> None:
    total = 0
    for path in sorted(ROOT.rglob("*.py")):
        items = find_deferred(path)
        if not items:
            continue
        rel = path.relative_to(ROOT.parent)
        print(f"\n{rel}:")
        for lineno, fn, text in items:
            print(f"  L{lineno}  in {fn}()  ->  {text}")
            total += 1
    print(f"\nTotal deferred lumitrade imports: {total}")


if __name__ == "__main__":
    main()
