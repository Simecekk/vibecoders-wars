# Vibecoders Wars

A beginner-friendly open-source game: together we build one FastAPI backend, one **area** at a time, through pull requests. Win an area with the most 👍 and approvals and it's yours on the map at [vibecoders.cz/valky](https://www.vibecoders.cz/valky/).

- **How to play:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Rules:** [docs/rules.md](docs/rules.md)
- **Game state:** [data/territories.json](data/territories.json) (schema: [schema/schema.json](schema/schema.json)), written only by the bot.

## Layout
```
app/main.py              FastAPI app, auto-discovers areas (maintainer)
app/areas/<id>/          one area = router.py with `router = APIRouter()`
tests/areas/<id>/        tests of the area
tests/conftest.py        "every endpoint has a test" check (maintainer)
scripts/check_pr.py      PR checks: title, paths, commits (CI)
scripts/check_imports.py no imports between areas (CI)
scripts/evaluate.py      daily evaluation at 20:00 Prague (cron)
scripts/validate_state.py validates data/territories.json
```

## Development
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Labels
`area:<id>`, `vv:invalid` (breaks the rules), `vv:lost` (lost the vote), `vv:blocked` (maintainer veto), `vv:fix` (fix in a claimed area; added by the bot to PRs titled `[fix:<area-id>] ...`).

License: [MIT](LICENSE).
