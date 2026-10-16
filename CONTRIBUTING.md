# How to play Vibecoders Wars (a guide for total beginners)

Never made a pull request? That's exactly what you'll learn here. The game rules are in [docs/rules.md](docs/rules.md).

## 1. GitHub account
Sign up at <https://github.com> (free). Tip: you can vote for others once your account is older than 30 days, but you can send a PR right away.

## 2. Fork
Open `https://github.com/Simecekk/vibecoders-wars` and click **Fork**. You get your own copy at `github.com/<your-login>/vibecoders-wars`.

## 3. Clone
You need [Git](https://git-scm.com) and Python 3.11+.
```bash
git clone https://github.com/<your-login>/vibecoders-wars.git
cd vibecoders-wars
```

## 4. New branch
Pick a free area (map at `vibecoders.cz/valky` or [docs/rules.md](docs/rules.md)), e.g. `validation`.
```bash
git checkout -b validation-my-solution
```

## 5. Run it locally
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest                           # everything should be green
uvicorn app.main:app --reload    # optional: open http://localhost:8000/docs to try your endpoints
```
Prefer Docker? `docker compose up --build` starts the app and `docker compose run --rm app pytest` runs the tests (see the [README](README.md#running-the-app)).

## 6. Write code and tests
- Code goes **only** into `app/areas/<area-id>/`. Start with `router.py` containing `router = APIRouter()`; your endpoints are served under `/<area-id>`. See `app/areas/_example/`.
- Tests go **only** into `tests/areas/<area-id>/`, e.g. `tests/areas/validation/test_validation.py`.
- Write at least one test for **every endpoint**. Use the `client` fixture:
```python
def test_create_item_rejects_empty_name(client):
    r = client.post("/validation/items", json={"name": ""})
    assert r.status_code == 422
```
- Run `VV_AREA=validation pytest` (that is what CI runs) and make sure everything is green.

## 7. Commit
```bash
git add app/areas/validation tests/areas/validation
git commit -m "Validate item name"
```
All commits must be **yours**: no commits by others and no `Co-authored-by`.

## 8. Push
```bash
git push -u origin validation-my-solution
```

## 9. Pull request
On GitHub click **Compare & pull request**. **The title must start with the area id in square brackets:**
```
[validation] Validate name and email
```
Describe what you did, then wait for CI (green check ✅). If it is red, fix the code, commit and push again; the PR updates itself.

## 10. Get votes
Share the PR link with friends:
- 👍 reaction on the PR = 1 point
- an **Approve** review = 2 points

Only accounts older than 30 days count. Each person can support only one PR per area. Your own vote doesn't count.

## 11. What happens at 20:00
Every day at 20:00 (Prague time) the bot evaluates the free areas. The PR with green CI and the most points (at least 1) **wins**: the bot merges it and the area is yours 🎉. The other PRs get the `vv:lost` label and are closed. No worries, try another area!

## Fixing someone else's area (`vv:fix`)
Found a bug in a claimed area? Open a PR titled `[fix:<area-id>] ...`, e.g. `[fix:validation] Reject empty email`. The bot adds the `vv:fix` label. Same rules as always (only the area's two folders, your own commits, a test for every endpoint). It is merged once the area owner or the maintainer approves it — 👍 don't count here. The owner keeps the area; you get +1 participation point (once per area). Fix PRs don't count toward your 2 open PRs.

## FAQ
- **Can I have more PRs open?** Yes, at most 2, each for a different area. You can own only 1 area per wave; if you win one, your other PR in that wave is closed (you keep the participation point).
- **What do I get if I lose?** 1 participation point (once per area) if the PR was valid and CI was green. Your very first such PR also earns the "First PR" badge.
- **Do I edit `app/main.py`?** No. Your area is loaded automatically. Don't import anything from other areas.
- **CI says `UNTESTED: GET /validation/items`.** No test calls that endpoint. Add one that calls it via `client`.
- **Can I change files outside my area?** No, CI rejects the PR.
- **Can I add my own `conftest.py`?** No. Fixtures come only from `tests/conftest.py` on main; CI rejects any `conftest.py` in a PR. Use the `client` fixture or helpers inside your test files.
- **CI is red and I don't know why.** Click "Details" on the check and read the pytest output. Feel free to ask in a PR comment.
- **My PR got `vv:invalid`.** The bot explains why in a comment (usually a wrong title or files outside the area). Fix it and the bot checks again.
- **What is `vv:blocked`?** The maintainer's veto against cheating or broken PRs. Such a PR is not evaluated. For cheating, the maintainer can take away points and the area.
- **A friend helped me, can I add them as co-author?** No. The PR must be entirely yours, but your friend can give you a 👍 or a review.
- **Why doesn't the backend run anywhere?** It doesn't need to. The game is about learning Git and tests; green tests are enough.
