""""Every endpoint has a test" check (maintainer-owned).

A middleware records every request as (method, route template). When the session
finishes, the record is compared with the areas' routes:
- `VV_AREA=<id>` (set by CI from the PR title): only `/<id>/...` is checked,
- no `VV_AREA`: all areas in `app/areas/` are checked.
skip/xfail are not allowed in the tests of the `VV_AREA` area.
"""

from __future__ import annotations

import os

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app, discover_areas

HIT: set[tuple[str, str]] = set()
AREAS = discover_areas()  # same router objects the app mounted (importlib cache)
ROUTE_AREA = {id(route): area for area, router in AREAS for route in router.routes}
SKIPPED_IN_AREA: list[str] = []


@app.middleware("http")
async def record(request, call_next):
    response = await call_next(request)
    route = request.scope.get("route")
    if route is not None:
        area = ROUTE_AREA.get(id(route))
        HIT.add((request.method, f"/{area}{route.path}" if area else route.path))
    return response


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _area() -> str | None:
    return os.environ.get("VV_AREA") or None


def _in_area(nodeid: str, area: str) -> bool:
    return nodeid.replace("\\", "/").startswith(f"tests/areas/{area}/")


def required_endpoints(area: str | None) -> set[tuple[str, str]]:
    """Endpoints of one area (or all areas) as (method, /<id><path>)."""
    return {
        (method, f"/{a}{r.path}")
        for a, router in AREAS
        if area is None or a == area
        for r in router.routes
        if isinstance(r, APIRoute)
        for method in r.methods
        if method != "HEAD"
    }


def pytest_collection_modifyitems(config, items):
    area = _area()
    if not area:
        return
    for item in items:
        if _in_area(item.nodeid, area) and (item.get_closest_marker("skip") or item.get_closest_marker("skipif")
                                              or item.get_closest_marker("xfail")):
            SKIPPED_IN_AREA.append(item.nodeid)


def pytest_runtest_logreport(report):
    area = _area()
    if area and _in_area(report.nodeid, area) and (report.skipped or hasattr(report, "wasxfail")):
        if report.nodeid not in SKIPPED_IN_AREA:
            SKIPPED_IN_AREA.append(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    if session.config.getoption("collectonly"):
        return
    # Only check runs that include the area tests (not e.g. `pytest scripts/tests`).
    if not any(str(a).replace("\\", "/").rstrip("/") in ("", ".", "tests") or "tests/areas" in str(a)
               for a in (session.config.args or ["."])):
        return
    failed = False
    missing = sorted(required_endpoints(_area()) - HIT)
    if missing:
        print("\nUntested endpoints:", *[f"UNTESTED: {m} {p}" for m, p in missing], sep="\n  ")
        failed = True
    if SKIPPED_IN_AREA:
        print("\nskip/xfail is not allowed in area tests:", *SKIPPED_IN_AREA, sep="\n  ")
        failed = True
    if failed:
        session.exitstatus = 1
