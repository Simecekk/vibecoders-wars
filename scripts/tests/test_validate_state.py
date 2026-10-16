import copy
from pathlib import Path

import pytest

from scripts.common import load_json
from scripts.validate_state import main, validate


@pytest.fixture
def fresh():
    # Frozen initial state: data/territories.json changes after every evaluation run.
    # Defined here (not in conftest.py) because CI replaces conftest.py with main's copy.
    return copy.deepcopy(load_json(Path(__file__).parent / "fixtures" / "initial_state.json"))


def test_data_file_is_valid(fresh):
    assert validate(fresh) == []


def test_example_fixture_is_valid(example):
    assert validate(example) == []


def test_initial_state_waves_1_and_2(fresh):
    wave1 = [t for t in fresh["territories"] if t["wave"] == 1]
    assert len(wave1) == 5 and all(t["status"] == "free" for t in wave1)
    assert [w["status"] for w in fresh["waves"]] == ["open", "locked"]
    assert fresh["players"] == [] and fresh["repo"] == "Simecekk/vibecoders-wars"


def test_duplicate_coordinates(fresh):
    fresh["territories"][1]["map"] = dict(fresh["territories"][0]["map"])
    assert any("duplicate map coordinates" in e for e in validate(fresh))


def test_duplicate_id(fresh):
    fresh["territories"][1]["id"] = fresh["territories"][0]["id"]
    assert any("duplicate territory id" in e for e in validate(fresh))


def test_schema_error_tier_points(fresh):
    fresh["territories"][0]["basePoints"] = 50
    assert any(e.startswith("schema:") for e in validate(fresh))


def test_wrong_path(fresh):
    fresh["territories"][0]["codePath"] = "app/areas/other/"
    assert any("codePath" in e for e in validate(fresh))


def test_score_must_match_ledger(example):
    example["players"][0]["score"] += 1
    assert any("ledger total" in e for e in validate(example))


def test_cli(capsys):
    assert main([]) == 0
