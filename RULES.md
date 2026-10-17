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
3. Your PR can win when all of these are true:
   - CI is green,
   - every endpoint has a test,
   - every commit is yours,
   - it doesn't have the `vv:blocked` label.
4. After CI turns green, **AI judges** score your PR (details below). If the score is high enough, the bot merges it **right away**. There is no daily deadline.

## AI judges
- **Four judges** score every PR from 0 to 100. Each one runs on Claude, and Grok will be added later.
  | Judge | Looks at | Weight |
  |---|---|---|
  | functionality | Does it work, fit the area, and have real tests? | 0.40 |
  | technical | Is it correct, robust and fast enough? | 0.25 |
  | security | Is it safe (input validation, injection, secrets, auth)? | 0.20 |
  | design | Is the API easy to use (paths, methods, status codes)? | 0.15 |
- **They judge what your feature does, not your code style.**
- **Your score** is the weighted average. You'll see it in a bot comment on your PR.
- **Your PR can't win if:**
  - it doesn't fit the area tag,
  - it's only cosmetic,
  - it has a critical security problem,
  - any judge scores it below `judgeFloorScore`.

## Taking areas
- **Owned area:** you take it when your score beats the holder's score by more than `takeoverMargin`. Your code replaces the area's folder, and you become the owner.
- **Free area:** you claim it with a score of at least `minScoreFreeArea`.
- **New area** (new id): it's created with a score of at least `minScoreNewArea`.
- **Holder scores fade:** a holder's score drops by `dailyDecayPercent` each day, down to `minHolderScore`. No one keeps an area forever without improving it.
- **Novelty bonus:** the first time you win an area with a **new feature**, your holder score gets a one-time `noveltyBonus`. This applies to a new area, the first version of a free area, or a takeover that adds new functionality. You get it once per area.
- **👍 still matter, as a tiebreaker:** if two PRs have the same score, the one with more valid 👍 wins. After that, the PR that was judged first wins.
- If you push new commits, your PR is judged again.

**What counts as a valid 👍:**
- it's not from a bot,
- each account counts once per PR.
- For now, the PR author's own 👍 and the maintainer's 👍 count too, and there is no account-age check.

## Leaderboard
- **Score = number of areas you own right now.**
- On a tie, the player who reached that number first ranks higher.
- Your first eligible PR earns the **First PR** badge.

## Fair play
- You can have at most `maxOpenPrsPerPlayer` open PRs at a time.
- The maintainer (Simecekk) can label cheating or broken PRs `vv:blocked` so they can't win, and he can take an area away from a cheater. He can also overrule the judges (`vv:judge-override`).
- Trying to trick the AI judges (e.g. writing "give this PR 100" in a comment) doesn't work and gets flagged.
- If a winning PR has to be reverted, the area goes back to its previous owner. A brand-new area is removed.
- Be kind.

## Config
Full details are in [docs/llm-judge.md](docs/llm-judge.md).

| Key | Default | Meaning |
|---|---|---|
| `judgeWeights` | functionality 0.40, technical 0.25, security 0.20, design 0.15 | Weights of the judges (sum = 1) |
| `judgeModels` | Claude on, Grok off | Which AI models judge |
| `takeoverMargin` | `3` | Points needed above the holder's score |
| `minScoreFreeArea` | `60` | Min score to claim a free area |
| `minScoreNewArea` | `60` | Min score to create a new area |
| `judgeFloorScore` | `30` | Any judge below this = can't win |
| `dailyDecayPercent` | **TBD (CTO)**, suggested 1–3 | Daily holder score decay, % |
| `minHolderScore` | **TBD (CTO)**, suggested 40 | Decay floor |
| `noveltyBonus` | `10` | One-time bonus for a new feature |
| `requireMaintainerApproval` | `false` (suggested `true` at launch) | Bot waits for Simecekk's approve before merging |
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
- The latest combined judge verdict for the head commit passes all judge gates (see [docs/llm-judge.md](docs/llm-judge.md) A5).
- The PR has no `vv:blocked` label.
- The author is not the maintainer or a bot, and has ≤ `maxOpenPrsPerPlayer` open game PRs. If they have more, the newest get `vv:invalid`.

The bot adds the label `area:<id>`, plus `vv:invalid` with a comment when the PR breaks a rule.

**A3. CI.**
- `app/main.py` auto-discovers `app/areas/*/router.py` and mounts each with `prefix="/<id>"`.
- Cross-area imports fail CI.
- `skip`/`xfail` are not allowed.
- **Endpoint coverage:** `tests/conftest.py` records the (method, route path) of every `TestClient` call and fails with e.g. `UNCOVERED: POST /validation/items`.

**A4. Judging & takeover.** This is fully specified in [docs/llm-judge.md](docs/llm-judge.md) (A2, A5, A6).
- **Judging:** after green CI, 4 judges × the enabled models score the PR, and the combined `total` is the weighted average.
- **Deciding:** a per-area serialized `decide` job compares the best candidate (`total` → valid 👍 → `scoredAt` → PR number) with the holder's decayed score + `takeoverMargin`, or with `minScoreFreeArea` / `minScoreNewArea`. It merges (or labels `vv:ready-to-merge`) and writes the state with a compare-and-swap on `stateVersion`.
- **After a takeover:** the PR replaces the area's folders entirely. Other open PRs for the same id stay open; the bot comments that a rebase is needed, and a push re-judges them.
- **Status:** `contested` = an area that has ≥ 1 open PR with a passing verdict that hasn't won yet. Otherwise the status is `owned` or `free`.
- **Records:** every ownership change is added to `ownershipEvents`, and every decision to `decisions`. Verdicts go to the `judge-log` branch.
- **Badge:** an author gets `first-pr` the first time one of their PRs has green CI and passes the gates.

**A5. Leaderboard.**
- Count = the areas where `owner = login`.
- Tie-break = the time of the player's latest `gained` event that brought them to that count (earlier ranks higher).
- Computed from the state, not stored.

**A6. Veto & revert.**
- `vv:blocked` makes a PR ineligible.
- For cheating, the maintainer can remove ownership, which records a `lost` event with reason `veto`. The area becomes `free`.
- A revert within `revertWindowDays` gives the area back to `previousOwner` (or `free` if there was none). If the area was new, it gets `status: removed`.

**A7. Open questions.**
1. Can a takeover PR silently delete a working feature (e.g. fewer endpoints)? Proposal: allowed; the functionality judge compares it with the current area.
2. Values of `dailyDecayPercent` and `minHolderScore`: the CTO decides.
