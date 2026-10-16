"""Forbid imports between areas.

Usage: python scripts/check_imports.py <area-id> [--root .]
Walks the AST of every .py in app/areas/<id>/ and tests/areas/<id>/ and fails if
it imports another area (`app.areas.<other-id>`), including `from app.areas import x`
and relative imports that climb out of the area (`from .. import x`).
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def _violations_in(source: str, area: str, rel_depth_limit: int) -> list[str]:
    out: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _foreign(alias.name, area):
                    out.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if node.level > rel_depth_limit:
                    out.append(f"from {'.' * node.level}{node.module or ''} import ...")
                continue
            mod = node.module or ""
            if _foreign(mod, area):
                out.append(f"from {mod} import ...")
            elif mod == "app.areas":
                for alias in node.names:
                    if alias.name != area:
                        out.append(f"from app.areas import {alias.name}")
        elif isinstance(node, ast.Call):
            # importlib.import_module("app.areas.x") / __import__("app.areas.x")
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in ("import_module", "__import__") and node.args and isinstance(node.args[0], ast.Constant):
                val = node.args[0].value
                if isinstance(val, str) and _foreign(val, area):
                    out.append(f"{name}({val!r})")
    return out


def _foreign(module: str, area: str) -> bool:
    parts = module.split(".")
    return len(parts) >= 3 and parts[0] == "app" and parts[1] == "areas" and parts[2] != area


def check(root: Path, area: str) -> list[str]:
    errors: list[str] = []
    for base in (root / "app" / "areas" / area, root / "tests" / "areas" / area):
        for py in sorted(base.rglob("*.py")):
            rel = py.relative_to(root)
            # a relative import may climb at most to the area root
            depth = len(py.relative_to(base).parts)
            try:
                found = _violations_in(py.read_text(encoding="utf-8"), area, depth)
            except SyntaxError as exc:
                errors.append(f"{rel}: syntax error: {exc.msg}")
                continue
            errors.extend(f"{rel}: forbidden import of another area: {v}" for v in found)
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("area")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    errors = check(Path(args.root), args.area)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    if not errors:
        print(f"OK: area {args.area} does not import other areas")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
