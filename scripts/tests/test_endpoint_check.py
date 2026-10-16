"""Acceptance test of tests/conftest.py: removing a test makes pytest fail with the untested endpoint."""

import os
import shutil
import subprocess
import sys

from scripts.common import ROOT


def run(tmp_path, area_env, drop_echo):
    for d in ("app", "tests", "data"):
        shutil.copytree(ROOT / d, tmp_path / d, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "pyproject.toml", tmp_path)
    shutil.copy(ROOT / "RULES.md", tmp_path)
    test = tmp_path / "tests/areas/_example/test_example.py"
    if drop_echo:
        test.write_text(test.read_text().split("def test_echo")[0])
    env = {**os.environ, "VV_AREA": area_env} if area_env else {k: v for k, v in os.environ.items() if k != "VV_AREA"}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-p", "no:cacheprovider"], cwd=tmp_path, env=env, capture_output=True, text=True
    )


def test_all_tested_passes(tmp_path):
    assert run(tmp_path, "_example", drop_echo=False).returncode == 0


def test_missing_test_fails_with_list(tmp_path):
    res = run(tmp_path, "_example", drop_echo=True)
    assert res.returncode == 1 and "UNTESTED: POST /_example/echo" in res.stdout


def test_missing_test_fails_without_area(tmp_path):
    assert run(tmp_path, None, drop_echo=True).returncode == 1


def test_skip_in_area_fails(tmp_path):
    (tmp_path / "tests/areas/_example").mkdir(parents=True)
    res = None
    for d in ("app", "tests", "data"):
        shutil.copytree(ROOT / d, tmp_path / d, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    shutil.copy(ROOT / "pyproject.toml", tmp_path)
    shutil.copy(ROOT / "RULES.md", tmp_path)
    (tmp_path / "tests/areas/_example/test_skip.py").write_text("import pytest\n\n@pytest.mark.skip\ndef test_later():\n    pass\n")
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-p", "no:cacheprovider"],
        cwd=tmp_path,
        env={**os.environ, "VV_AREA": "_example"},
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1 and "skip/xfail" in res.stdout
