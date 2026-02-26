from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src" / "rpg"


@dataclass(frozen=True)
class ImportEdge:
    source: str
    target: str
    type_checking_only: bool


def _path_to_module(path: Path) -> str:
    relative = path.relative_to(ROOT / "src")
    module = ".".join(relative.with_suffix("").parts)
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]
    return module


def _module_to_layer(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "rpg":
        return None
    if parts[1] in {"domain", "application", "infrastructure", "presentation"}:
        return parts[1]
    return None


def _has_future_annotations(tree: ast.AST) -> bool:
    if not isinstance(tree, ast.Module):
        return False
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            return any(alias.name == "annotations" for alias in node.names)
        break
    return False


def _uses_type_checking(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
            return True
    return False


def _resolve_relative_module(current_module: str, module: str | None, level: int) -> str | None:
    if level == 0:
        return module

    base_parts = current_module.split(".")
    if len(base_parts) < level:
        return None
    prefix = base_parts[:-level]
    if module:
        return ".".join(prefix + module.split("."))
    return ".".join(prefix)


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, current_module: str) -> None:
        self._current_module = current_module
        self._type_checking_depth = 0
        self.edges: list[ImportEdge] = []

    def _record(self, target: str) -> None:
        if target:
            self.edges.append(
                ImportEdge(
                    source=self._current_module,
                    target=target,
                    type_checking_only=self._type_checking_depth > 0,
                )
            )

    def visit_If(self, node: ast.If) -> None:
        is_type_checking_guard = (
            isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
        )
        if is_type_checking_guard:
            self._type_checking_depth += 1
            for child in node.body:
                self.visit(child)
            self._type_checking_depth -= 1
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        resolved = _resolve_relative_module(
            current_module=self._current_module,
            module=node.module,
            level=node.level,
        )
        if resolved:
            self._record(resolved)


def _load_module_graph() -> tuple[dict[str, Path], list[ImportEdge], dict[str, ast.AST]]:
    module_files: dict[str, Path] = {}
    parsed_trees: dict[str, ast.AST] = {}

    for path in SRC_ROOT.rglob("*.py"):
        module_name = _path_to_module(path)
        module_files[module_name] = path
        parsed_trees[module_name] = ast.parse(path.read_text(encoding="utf-8-sig"))

    known_modules = set(module_files.keys())
    edges: list[ImportEdge] = []

    for module_name, tree in parsed_trees.items():
        collector = _ImportCollector(current_module=module_name)
        collector.visit(tree)
        for edge in collector.edges:
            if not edge.target.startswith("rpg"):
                continue

            target = edge.target
            while target and target not in known_modules and "." in target:
                target = target.rsplit(".", 1)[0]

            if target in known_modules and target != module_name:
                edges.append(
                    ImportEdge(
                        source=module_name,
                        target=target,
                        type_checking_only=edge.type_checking_only,
                    )
                )

    return module_files, edges, parsed_trees


def _find_cycle(graph: dict[str, set[str]]) -> list[str]:
    state: dict[str, int] = {}
    stack: list[str] = []

    def dfs(node: str) -> list[str]:
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, set()):
            nxt_state = state.get(nxt, 0)
            if nxt_state == 0:
                cycle = dfs(nxt)
                if cycle:
                    return cycle
            elif nxt_state == 1:
                idx = stack.index(nxt)
                return stack[idx:] + [nxt]
        stack.pop()
        state[node] = 2
        return []

    for node in sorted(graph.keys()):
        if state.get(node, 0) == 0:
            cycle = dfs(node)
            if cycle:
                return cycle
    return []


class ArchitectureGuardrailTests(unittest.TestCase):
    def test_domain_layer_does_not_import_upstream_layers(self) -> None:
        module_files, edges, _ = _load_module_graph()
        violations: list[str] = []

        for edge in edges:
            source_layer = _module_to_layer(edge.source)
            target_layer = _module_to_layer(edge.target)
            if source_layer != "domain":
                continue
            if target_layer in {"application", "infrastructure", "presentation"}:
                source_path = module_files[edge.source].relative_to(ROOT)
                target_path = module_files[edge.target].relative_to(ROOT)
                violations.append(f"{source_path} -> {target_path}")

        self.assertEqual([], violations, "Domain layer imports forbidden upstream layers")

    def test_runtime_import_graph_has_no_cycles(self) -> None:
        modules, edges, _ = _load_module_graph()
        graph: dict[str, set[str]] = {module: set() for module in modules.keys()}

        for edge in edges:
            if edge.type_checking_only:
                continue
            graph[edge.source].add(edge.target)

        cycle = _find_cycle(graph)
        self.assertEqual([], cycle, f"Import cycle detected: {' -> '.join(cycle)}")

    def test_type_checking_usage_requires_future_annotations(self) -> None:
        module_files, _, trees = _load_module_graph()
        violations: list[str] = []

        for module_name, tree in trees.items():
            if not _uses_type_checking(tree):
                continue
            if not _has_future_annotations(tree):
                violations.append(str(module_files[module_name].relative_to(ROOT)))

        self.assertEqual([], violations, "TYPE_CHECKING usage requires 'from __future__ import annotations'")


if __name__ == "__main__":
    unittest.main()
