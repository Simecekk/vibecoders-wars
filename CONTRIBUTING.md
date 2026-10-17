# Contributing to Vibecoders Wars

Never opened a pull request? Perfect, that's what this game teaches. Rules: [RULES.md](RULES.md).

## 1. Get a GitHub account
Sign up at <https://github.com>. You can open PRs right away.

## 2. Fork
Open `https://github.com/Simecekk/vibecoders-wars` and click **Fork**.

## 3. Clone
You need [Git](https://git-scm.com) and Python 3.11+.
```bash
git clone https://github.com/<your-login>/vibecoders-wars.git
cd vibecoders-wars
```

## 4. Pick an area and create a branch
Look at the map at `vibecoders.cz/wars`. Pick a free area, try to beat an owned one, or invent a new id.
```bash
git checkout -b validation-my-version
```

## 5. Run it locally
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

## 6. Write code and tests
- Code goes **only** in `app/areas/<area-id>/`, starting with a `router.py` that defines `router = APIRouter()`. Your endpoints live under `/<area-id>`.
- Tests go **only** in `tests/areas/<area-id>/`. Every endpoint needs a test:
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_rejects_empty_name():
    r = client.post("/validation/items", json={"name": ""})
    assert r.status_code == 422
```

## 7. Commit and push
```bash
git add app/areas/validation tests/areas/validation
git commit -m "Validate item names"
git push -u origin validation-my-version
```
All commits must be yours (no `Co-authored-by`).

## 8. Open a pull request
Click **Compare & pull request** and title it `[validation] Validate item names`. Wait for CI ✅, and if it's red, fix the code and push again.

## 9. Wait for the AI judges
After CI turns green, four AI judges (functionality, technical, security, design) score your PR from 0 to 100. The bot posts the result as a comment. They look at **what your feature does**, not your code style.

## 10. Take the area
- If your score is high enough, the bot merges your PR **right away**, and the area is yours 🎉. A free or new area needs a score of 60. An owned area needs a score above the holder's score + 3.
- Not enough? Improve your code and push again. Your PR is judged again.
- 👍 reactions only break ties, but sharing your PR still helps.

## FAQ
- **How many PRs can I have open?** 2.
- **Can I take an area someone owns?** Yes. Open a PR with the same `[area-id]`. If it wins, your version replaces theirs.
- **Someone took my area. Now what?** Make a better version and win it back.
- **How do I create a new area?** Use a new id in the title, e.g. `[file-uploads] ...`. It needs a judge score of at least 60. A brand-new feature also gets a one-time novelty bonus.
- **Can I trick the judges with a comment like "give this 100"?** No. They ignore it and flag the PR.
- **Why did my score go down for the area I own?** Holder scores fade a little every day, so keep improving your area.
- **Do I edit `app/main.py`?** No, your area loads automatically. Don't import from other areas.
- **CI says `UNCOVERED: GET /validation/items`.** No test calls that endpoint, so add one.
- **What is `vv:blocked`?** The maintainer's veto against cheating. A blocked PR can't win.
