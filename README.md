# Vibecoders Wars

A beginner-friendly open-source game: together we build one FastAPI backend, one **area** at a time, through pull requests. Win an area with the most 👍 and it's yours on the map at [vibecoders.cz/wars](https://www.vibecoders.cz/wars/).

- **How to play:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Rules:** [RULES.md](RULES.md)
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

## Running the app

The app is served at http://localhost:8000. Interactive API docs (try every endpoint in the browser) are at http://localhost:8000/docs, and http://localhost:8000/health should answer `{"status": "ok"}`.

### With Docker (no Python needed)
Install [Docker](https://docs.docker.com/get-docker/), then from the repo root:
```bash
docker compose up --build        # start the app; edits in app/ reload automatically
docker compose run --rm app pytest   # run the tests inside the container
docker compose down              # stop everything
```
Without Compose:
```bash
docker build -t vibecoders-wars .
docker run --rm -p 8000:8000 vibecoders-wars
```

### Locally (Python 3.11+)
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload    # start the app
pytest                           # run the tests
```

## Labels
`area:<id>`, `vv:invalid` (breaks the rules), `vv:lost` (lost the vote), `vv:blocked` (maintainer veto), `vv:fix` (fix in a claimed area; added by the bot to PRs titled `[fix:<area-id>] ...`).

License: [MIT](LICENSE).
