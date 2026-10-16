# Vibecoders Wars — rules

A game for beginners: learn **fork, branch, commit, pull request and review** while building a piece of a real backend.

## The idea
- Together we build **one FastAPI backend** in `Simecekk/vibecoders-wars`. It doesn't run anywhere; passing tests are enough.
- The backend is split into **areas** (e.g. "validation" or "caching"). Code: `app/areas/<area-id>/` (its own `APIRouter`, served under `/<area-id>/...`). Tests: `tests/areas/<area-id>/`.
- Areas are independent modules: the app finds them automatically; you never edit `app/main.py` and never import from other areas.
- When your PR wins an area, **the area is yours** and your avatar shows up on the map at `vibecoders.cz/valky`.

## Points
| Tier | Points |
|---|---|
| S (easy) | 10 |
| M (medium) | 25 |
| L (hard) | 50 |

You get the points when you win an area. A valid PR with green CI that loses earns **1 participation point** (at most once per area). Your first valid PR with green CI earns the **"First PR"** badge.

## Waves
Areas unlock in waves. The next wave opens once every area of the current one has an owner.

**Wave 1:** `crud-endpoints` (S), `validation` (S), `error-handling` (S), `database-models` (M), `middleware-logging` (M).
**Wave 2 (locked):** `pagination-filtering` (S), `testing-fixtures` (M), `caching` (M), `background-tasks` (M), `rate-limiting` (M), `auth` (L).

## How to claim an area
1. Fork, branch, put code **only** into `app/areas/<area-id>/` and tests **only** into `tests/areas/<area-id>/`.
2. Open a PR whose title starts with `[area-id]`, e.g. `[validation] Validate user signup`.
3. CI must be green, **every endpoint** needs at least one test, and **all commits are yours** (no co-authors).
4. Ask friends for a 👍 or an approve review.

## Daily evaluation at 20:00 (Prague)
For every open area the bot adds up the points of PRs with green CI: **👍 = 1 point, approve review = 2 points**.
Votes count only from accounts that are not the PR author, not a bot, not the maintainer, and older than 30 days.
Each account votes only **once per area** — its earliest vote counts. 👍 and approve on the same PR add up.

**The PR with the most points wins** (at least 1 point; ties go to the older PR). The bot merges it; the other PRs for that area get `vv:lost`, a friendly comment and are closed. With no points, the area waits for the next evening.

## Limits and fair play
- You can own **at most 1 area per wave** and have **at most 2 open PRs**, each for a different area.
- `vv:blocked` (maintainer veto): the PR is not evaluated. For cheating the maintainer can take away points and the area; every such action is visible in the points history.
- If your winning code has to be reverted within 7 days, you lose the area and the points.
- Fixes in someone else's area: title the PR `[fix:<area-id>] ...`; the bot labels it `vv:fix`. It is merged after an approve from the area owner or the maintainer, the owner keeps the area and the fix author gets +1 participation (once per area). Fix PRs are not part of the daily vote.
- PRs may not contain any `conftest.py`; test fixtures come only from main.
- Be kind: the [Code of Conduct](../CODE_OF_CONDUCT.md) applies.
