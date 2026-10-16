from scripts.check_imports import check


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_own_imports_ok(tmp_path):
    write(tmp_path, "app/areas/validation/router.py", "from app.areas.validation import models\nfrom . import x\nimport fastapi\n")
    assert check(tmp_path, "validation") == []


def test_import_other_area(tmp_path):
    write(tmp_path, "app/areas/validation/router.py", "from app.areas.caching.router import cache\n")
    assert "app.areas.caching" in check(tmp_path, "validation")[0]


def test_import_other_area_variants(tmp_path):
    write(tmp_path, "app/areas/validation/a.py", "import app.areas.auth\n")
    write(tmp_path, "app/areas/validation/b.py", "from app.areas import auth\n")
    write(tmp_path, "app/areas/validation/c.py", "from .. import auth\n")
    write(tmp_path, "tests/areas/validation/test_x.py", "import importlib\nimportlib.import_module('app.areas.auth')\n")
    assert len(check(tmp_path, "validation")) == 4


def test_syntax_error_reported(tmp_path):
    write(tmp_path, "app/areas/validation/router.py", "def (:\n")
    assert "syntax error" in check(tmp_path, "validation")[0]
