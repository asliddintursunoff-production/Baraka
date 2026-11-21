"""The Financial Engine is pure Python: no Django, ORM, network or SDK imports."""

import ast
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "apps" / "engine"
FORBIDDEN = ("django", "rest_framework", "google", "requests", "httpx", "psycopg", "apps.")


def test_engine_source_has_no_forbidden_imports():
    for path in ENGINE.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            for name in names:
                assert not name.startswith(FORBIDDEN) or name.startswith("apps.engine"), (
                    f"{path.name} imports {name}"
                )


def test_engine_imports_without_django_loaded():
    code = (
        "import sys, importlib, pkgutil, apps.engine as e\n"
        "for m in pkgutil.walk_packages(e.__path__, 'apps.engine.'):\n"
        "    importlib.import_module(m.name)\n"
        "assert not any(k == 'django' or k.startswith('django.') for k in sys.modules), 'django loaded'\n"
    )
    root = ENGINE.parent.parent
    subprocess.run([sys.executable, "-c", code], cwd=root, check=True)
