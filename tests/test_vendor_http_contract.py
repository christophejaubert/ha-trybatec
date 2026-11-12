"""Static regression contract: vendor HTTP remains read-only except login.

This AST test never imports the vendor client and makes no HTTP requests.
It complements mocked runtime tests; dynamic dispatch requires code review.
"""
from __future__ import annotations

import ast
from pathlib import Path

INTEGRATION = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
NETWORK_METHODS = {"get", "post", "put", "patch", "delete", "request"}


class VendorHttpVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions: list[str] = []
        self.operations: list[tuple[str, str, str]] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in NETWORK_METHODS
            and isinstance(func.value, ast.Attribute)
            and func.value.attr in {"session", "_session"}
        ):
            target = ast.unparse(node.args[0]) if node.args else ""
            self.operations.append(
                (self.functions[-1] if self.functions else "", func.attr, target)
            )
        self.generic_visit(node)


def policy_violations(path: Path, source: str) -> list[str]:
    visitor = VendorHttpVisitor()
    visitor.visit(ast.parse(source, filename=str(path)))
    violations: list[str] = []
    for function, method, target in visitor.operations:
        if method == "get":
            continue
        if (
            method == "post"
            and path.name == "api.py"
            and function == "authenticate"
            and "/authenticate" in target
        ):
            continue
        violations.append(f"{path.name}: unexpected vendor HTTP method {method}")
    return violations


def test_vendor_calls_allow_only_authentication_post_and_get():
    files = sorted(INTEGRATION.glob("*.py"))
    assert files, "Integration sources were not found"
    failures: list[str] = []
    for path in files:
        failures.extend(policy_violations(path, path.read_text(encoding="utf-8")))
    assert not failures, "\n".join(failures)


def test_mutation_calls_are_rejected_even_in_new_client_methods():
    code = (
        "class Client:\n"
        "    async def update(self):\n"
        "        await self._session.post('https://example.invalid/api/v1/indexes')\n"
        "        await self._session.put('https://example.invalid/api/v1/device')\n"
        "        await self._session.delete('https://example.invalid/api/v1/device')\n"
        "        await self._session.request('PATCH', 'https://example.invalid')\n"
    )
    result = policy_violations(Path("api.py"), code)
    assert len(result) == 4
    assert "post" in result[0]
    assert "put" in result[1]
    assert "delete" in result[2]
    assert "request" in result[3]


def test_authenticated_post_is_only_whitelisted_for_authenticate():
    source = (
        "class Client:\n"
        "    async def authenticate(self):\n"
        "        await self._session.post(f'{API_BASE}/authenticate')\n"
    )
    assert policy_violations(Path("api.py"), source) == []
    assert policy_violations(Path("other.py"), source)
