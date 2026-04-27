"""Track 4: Backend circular dependency scan.

Builds a module-level import graph from the lumitrade package and finds all
strongly connected components (cycles) using Tarjan's algorithm.

Reports both module-level cycles (file-import-time) and module-pair cycles.
Excludes imports that occur inside function bodies (those are intentional
deferred imports per CLAUDE.md, e.g. main.py:192).
"""
from __future__ import annotations

import ast
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent / "lumitrade"
PKG = "lumitrade"


def _module_name_for(path: Path) -> str:
    rel = path.relative_to(ROOT.parent).with_suffix("")
    parts = rel.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_relative(current_module: str, level: int, module: str | None) -> str | None:
    parts = current_module.split(".")
    # current_module includes the file's own name; for relative resolution we
    # need to walk up `level` ancestors of the *package* the file lives in.
    # In Python, `from .foo import x` from package a.b.c means a.b.foo.
    # So strip `level` parts (the file's own name counts as level 1's anchor).
    if level > len(parts):
        return None
    base = parts[: len(parts) - level]
    if module:
        base = base + module.split(".")
    if not base:
        return None
    return ".".join(base)


def _collect_top_level_imports(tree: ast.AST, current_module: str) -> set[str]:
    """Return all lumitrade.* modules imported at top-level (not inside def/async def)."""
    imports: set[str] = set()

    class V(ast.NodeVisitor):
        def __init__(self) -> None:
            self.depth = 0  # 0 = module level

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            # Skip - imports inside functions are deferred (intentional)
            return

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            return

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                if alias.name.startswith(PKG + ".") or alias.name == PKG:
                    imports.add(alias.name)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if node.level and node.level > 0:
                resolved = _resolve_relative(current_module, node.level, node.module)
                if resolved and resolved.startswith(PKG):
                    # Also consider what they import — could be submodules
                    imports.add(resolved)
                    for alias in node.names:
                        sub = f"{resolved}.{alias.name}"
                        imports.add(sub)
            elif node.module and (node.module.startswith(PKG + ".") or node.module == PKG):
                imports.add(node.module)
                for alias in node.names:
                    imports.add(f"{node.module}.{alias.name}")

    V().visit(tree)
    return imports


def build_graph() -> tuple[dict[str, set[str]], set[str]]:
    """Build module -> {imported modules} graph (module = .py file)."""
    # First, collect all real module names (so we can normalize "imports of names" down to module).
    real_modules: set[str] = set()
    file_for_module: dict[str, Path] = {}
    for path in ROOT.rglob("*.py"):
        mod = _module_name_for(path)
        real_modules.add(mod)
        file_for_module[mod] = path

    graph: dict[str, set[str]] = defaultdict(set)
    for mod, path in file_for_module.items():
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(path))
        except SyntaxError as e:
            print(f"SYNTAX ERROR in {path}: {e}", file=sys.stderr)
            continue
        imports = _collect_top_level_imports(tree, mod)
        for imp in imports:
            # Normalize: pick the longest prefix that matches a real module.
            target = None
            cand = imp
            while cand:
                if cand in real_modules:
                    target = cand
                    break
                if "." not in cand:
                    break
                cand = cand.rsplit(".", 1)[0]
            if target and target != mod:
                graph[mod].add(target)
    return graph, real_modules


def tarjan_scc(graph: dict[str, set[str]], nodes: set[str]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in graph.get(v, ()):
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])
        if lowlink[v] == indices[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    sys.setrecursionlimit(10000)
    for v in nodes:
        if v not in indices:
            strongconnect(v)
    return sccs


def find_short_cycles(graph: dict[str, set[str]], scc: list[str]) -> list[list[str]]:
    """Within an SCC, enumerate simple cycles up to length 6 for reporting."""
    members = set(scc)
    cycles: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    LIMIT = 6

    def dfs(start: str, current: str, path: list[str]) -> None:
        if len(path) > LIMIT:
            return
        for nxt in graph.get(current, ()):
            if nxt not in members:
                continue
            if nxt == start and len(path) >= 1:
                # Found a cycle
                norm = tuple(path)
                # rotation-canonical
                k = norm.index(min(norm))
                rot = norm[k:] + norm[:k]
                if rot not in seen:
                    seen.add(rot)
                    cycles.append(list(norm) + [start])
            elif nxt not in path:
                dfs(start, nxt, path + [nxt])

    if len(scc) <= 12:
        for v in scc:
            dfs(v, v, [v])
    return cycles


def main() -> int:
    graph, modules = build_graph()
    sccs = tarjan_scc(graph, modules)
    cyclic = [s for s in sccs if len(s) > 1 or (len(s) == 1 and s[0] in graph.get(s[0], set()))]

    print(f"Total modules: {len(modules)}")
    print(f"Total internal edges: {sum(len(v) for v in graph.values())}")
    print(f"SCCs with size>1 (cycles): {len(cyclic)}")
    print()

    if not cyclic:
        print("RESULT: No top-level circular imports detected.")
        return 0

    for i, comp in enumerate(sorted(cyclic, key=len, reverse=True), 1):
        print(f"--- Cycle component #{i} (size {len(comp)}) ---")
        for m in sorted(comp):
            print(f"  {m}")
        cycles = find_short_cycles(graph, comp)
        if cycles:
            print("  Sample cycle paths:")
            for c in cycles[:5]:
                print("    " + " -> ".join(c))
        print()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
