# Vibecoders Wars — Rules

> A hobby game for beginners. Learn **fork, branch, commit, pull request and review** while building one FastAPI backend together.

## The idea
- We build **one FastAPI backend** in `Simecekk/vibecoders-wars`. Green tests are enough; it doesn't need to run anywhere.
- The backend is made of **areas**. An area is one feature in its own folder:
  - code: `app/areas/<area-id>/` with a `router.py` containing `router = APIRouter()`, served under `/<area-id>/...`
  - tests: `tests/areas/<area-id>/`
- Every area is open from day one, and anyone can create a new one.
- If you own an area, your avatar is on the map.

## Starting areas (all free)
`crud-endpoints`, `validation`, `error-handling`, `database-models`, `middleware-logging`, `pagination-filtering`, `testing-fixtures`, `caching`, `background-tasks`, `rate-limiting`, `auth`

## How to play
1. Fork, create a branch, and change **only** `app/areas/<area-id>/` and `tests/areas/<area-id>/`.
2. Open a PR titled `[<area-id>] Short description`.
   - If you use an existing id, you're trying to **take over** that area with your version.
   - If you use a new id (lowercase, dashes), you're creating a **new area**.
3. Your PR is eligible when all of these are true:
   - CI is green,
   - every endpoint has a test,
   - every commit is yours,
   - it doesn't have the `vv:blocked` label.
4. Collect 👍 reactions on your PR.

## Daily winner
- Every day at **20:00 Prague time**, **one PR wins**: the eligible PR with the most valid 👍. If two are tied, the older PR wins.
- **Existing area:** your code replaces that area's folder, and you become the owner.
- **New area:** it's created and you own it.
- Either way, the winner needs at least the minimum likes from the Config table.
- PRs that didn't win **stay open and keep their 👍**, so they compete again tomorrow.

**What counts as a valid 👍:**
- it's not from the PR author,
- it's not from a bot,
- the account is older than `minAccountAgeDays`,
- each account counts once per PR.

## Leaderboard
- **Score = number of areas you own right now.**
- On a tie, the player who reached that number first ranks higher.
- Your first eligible PR earns the **First PR** badge.

## Fair play
- You can have at most `maxOpenPrsPerPlayer` open PRs at a time.
- The maintainer (Simecekk) doesn't vote but can label cheating or broken PRs `vv:blocked`. Those PRs can't win, and he can take an area away from a cheater.
- If a winning PR has to be reverted, the area goes back to its previous owner. A brand-new area is removed.
- Be kind.

## Config
| Key | Default | Meaning |
|---|---|---|
| `evaluationTime` | `20:00` | Daily judging time |
| `timezone` | `Europe/Prague` | Time zone for judging |
| `winnersPerDay` | `1` | PRs merged per day |
| `minLikesNewArea` | `1` | Min valid 👍 to create a new area |
| `minLikesTakeover` | `1` | Min valid 👍 to take over an existing area |
| `minAccountAgeDays` | `30` | Voter account must be older than this |
| `maxOpenPrsPerPlayer` | `2` | Open game PRs per player |
| `revertWindowDays` | `7` | A revert within this window undoes the win |

---

# Appendix A — Bot & CI spec (for the CTO)

**A1. State.** `data/territories.json` (schema: `game/schema.json`, including `gameConfig`) is written only by the bot. The repo is private until the prototype works, so the bot publishes a public copy for the web.

**A2. Eligible PR.**
- The title matches `^\[([a-z0-9][a-z0-9-]*)\] ` and the id is not reserved (`main`, `core`, `shared`).
- The diff touches only `app/areas/<id>/**` and `tests/areas/<id>/**`.
- Every commit author is the PR author, with no `Co-authored-by`.
- CI is green on the head commit.
- The PR has no `vv:blocked` label.
- The author is not the maintainer or a bot, and has ≤ `maxOpenPrsPerPlayer` open game PRs. If they have more, the newest get `vv:invalid`.

The bot adds the label `area:<id>`, plus `vv:invalid` with a comment when the PR breaks a rule.

**A3. CI.**
- `app/main.py` auto-discovers `app/areas/*/router.py` and mounts each with `prefix="/<id>"`.
- Cross-area imports fail CI.
- `skip`/`xfail` are not allowed.
- **Endpoint coverage:** `tests/conftest.py` records the (method, route path) of every `TestClient` call and fails with e.g. `UNCOVERED: POST /validation/items`.

**A4. Judging.**
- **Schedule:** two UTC crons (`0 18 * * *`, `0 19 * * *`). The job exits unless the local time in `timezone` is `evaluationTime`. Runs may start a few minutes late, and votes count up to the job start.
- **Votes:** `+1` reactions on the PR, filtered by the voter rules and counted once per account.
- **Threshold:** each eligible PR needs ≥ `minLikesTakeover` valid 👍 if its id exists, or ≥ `minLikesNewArea` if the id is new.
- **Ranking:** most 👍 first, then the earlier `createdAt`, then the lower PR number. The top `winnersPerDay` PRs win, with no two winners for the same id on the same day.
- **Winner:** the bot squash-merges it. The PR replaces the area's folders entirely, so it should delete and re-add the files; when it's merged, `app/areas/<id>/` equals the PR version. The area's owner becomes the author: `status` = `owned`, `currentPr` is set and `previousOwner` is kept. For a new id, the bot creates the area and gives it the next hex in the spiral.
- **After a takeover:** other open PRs for the same id stay open. The bot comments that the base changed and that they need to rebase to stay green.
- **Losers** stay open and keep their votes. Nothing is closed automatically.
- **Status:** `contested` = an area that has ≥ 1 open eligible PR with ≥ 1 valid 👍. Otherwise the status is `owned` (has an owner) or `free`.
- **Records:** each run is stored in `evaluations`, and every ownership change is added to `ownershipEvents`. Runs are idempotent.
- **Badge:** an author gets `first-pr` the first time one of their PRs is eligible.

**A5. Leaderboard.**
- Count = the areas where `owner = login`.
- Tie-break = the time of the player's latest `gained` event that brought them to that count (earlier ranks higher).
- Computed from the state, not stored.

**A6. Veto & revert.**
- `vv:blocked` makes a PR ineligible.
- For cheating, the maintainer can remove ownership, which records a `lost` event with reason `veto`. The area becomes `free`.
- A revert within `revertWindowDays` gives the area back to `previousOwner` (or `free` if there was none). If the area was new, it gets `status: removed`.

**A7. Open questions.**
1. Can a takeover PR silently delete a working feature (e.g. fewer endpoints)? Proposal: allowed; votes decide.
2. Is the veto enough against vote rings of old accounts?
