# Vibecoders Wars

A beginner-friendly open-source game: together we build one FastAPI backend, one **area** at a time, through pull requests. AI judges score every PR; a high enough score takes the area right away. Map: [vibecoders.cz/wars](https://www.vibecoders.cz/wars/).

- **How to play:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Rules:** [RULES.md](RULES.md)
- **LLM judges:** [docs/llm-judge.md](docs/llm-judge.md)
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

The app is served at http://localhost:8000: the home page shows the area map, leaderboard and rules, and http://localhost:8000/rules has the rules on their own. Interactive API docs (try every endpoint in the browser) are at http://localhost:8000/docs, and http://localhost:8000/health should answer `{"status": "ok"}`.

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

Every pull request runs the same checks in CI; run them before you push:
```bash
ruff format .                    # format the code (CI runs `ruff format --check`)
ruff check .                     # lint
pytest --cov                     # tests; fails if coverage of app/ and scripts/ is below 80%
```

## Labels
`area:<id>`, `vv:invalid` (breaks the rules), `vv:blocked` (maintainer veto), `vv:ready-to-merge` (waiting for maintainer approve when required), `vv:judge-override` / `vv:judge-rejudge` / `vv:judge-disagree` / `vv:judge-injection` / `vv:judge-error` (LLM judge labels; see [docs/llm-judge.md](docs/llm-judge.md)).

License: [MIT](LICENSE).
