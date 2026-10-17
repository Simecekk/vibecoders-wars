# Vibecoders Wars — LLM judges (spec v0.1)

> Player-facing summary in plain English; technical appendix for the CTO.
> Related files (in the game package / to be added by the maintainer): prompts in `judge-prompts/` (`common.md` + 4 judges), verdict schema `judge-verdict.schema.json`, examples `judge-verdict.example.json` and `judge-combined.example.json`.

## How it works (in short)
- Every PR titled `[<area-id>]` is scored by **4 specialized judges**, each with its own prompt. The same prompt goes to **Claude and Grok**, each separately and independently. We start with **Claude only**; Grok is turned on with one config line.
  | Judge | Looks at | Weight |
  |---|---|---|
  | **functionality** | Does it work, fit the area tag, have meaningful tests, is it more than cosmetics, is it a new feature? | **0.40** |
  | **technical** | Correctness, robustness, maintenance risk, performance (outcome, not formatting) | **0.25** |
  | **security** | Input validation, injection, secrets, authz, abuse | **0.20** |
  | **design** | API design: paths, HTTP methods, status codes, response shape, usability | **0.15** |
- **Code style is not judged.** Outcome and behaviour are.
- **Overall PR score** = weighted average of the judge scores (0–100). For each judge, Claude's and Grok's scores are averaged.
- **Hard gates.** If any gate fails, the PR cannot take anything:
  - green CI and a test for every endpoint (still enforced in CI),
  - `matchesArea` (fits the tag),
  - `notCosmetic` (not cosmetics only),
  - no critical security finding,
  - no judge below `judgeFloorScore`.

## Taking areas (continuously, no 20:00)
Daily evaluation at 20:00 and winning by 👍 **are gone**. An area is taken continuously, right after judging:
- **Owned area:** a PR takes it when its score > **the holder's current score** + `takeoverMargin` (3 points).
- **Free area** (seed topics) is claimed at score ≥ `minScoreFreeArea`.
- **New area** is created at score ≥ `minScoreNewArea`.
- **Merge:** the bot merges automatically unless the PR has `vv:blocked`. With `requireMaintainerApproval: true`, the bot only labels `vv:ready-to-merge` and waits for Simecekk's approve.
- **👍 remain only as a tiebreaker.** There is no like bonus and no daily vote: GitHub Actions cannot trigger a workflow on a reaction, so a bonus would need polling and scores would drift on their own.

### Holder scores age
- Each day the holder loses `dailyDecayPercent` % (value set by the **CTO**; suggested 1–3 % per day), but not below `minHolderScore`. That way an area does not freeze forever under the first good PR.
- Computed on the fly at decision time, with no cron:
  `holderScore = max(minHolderScore, base × (1 − d)^wholeDays)`.

### Novelty bonus
- Whoever **first** wins an area with a **new feature** gets a one-time `noveltyBonus` (+10 points) on the holder base score. The bonus then ages normally.
- **A new feature means:**
  - a new area,
  - the first implementation of a free area,
  - a takeover where the functionality judge says `isNewFeature: true`.
- The bonus is given **once per player and area**. It is not used in the takeover comparison: a challenger always compares their raw score.

### Two PRs at once
- Each area is decided **serially, one run after another**.
- **Order:** higher score wins. On a tie, more valid 👍, then earlier judge time, then lower PR number.
- The **losing PR** is then compared with the **new** holder and must beat them by the margin.
- A **new push** = a new judgement and a new timestamp.

### Prompt or model change
- Scores are comparable only under the same judge set (hash of prompts, models and weights).
- On a change, **all holders are re-judged** from the area as it currently looks on main, and all open PRs too.
- Takeovers pause until that finishes. Decay and the novelty bonus stay.

## Maintainer review and overrides
- Every PR gets a **comment with the verdict** (judge table, gates, total score, and what is needed to take over) plus labels.
- **Labels:**
  - `vv:blocked`: veto; the PR cannot take anything.
  - `vv:judge-override`: overrides the judge gates (not CI).
  - `vv:judge-rejudge`: forces a new judgement.
  - `vv:judge-disagree`: models disagree a lot.
  - `vv:judge-injection`: a judge caught a prompt-manipulation attempt.
  - `vv:judge-error`: a judge failed.
- **Audit:** every verdict (model, version, prompt + hash, inputs, raw and parsed output, tokens) is stored on the `judge-log` branch.
- **Consistency:**
  - a sample of verdicts is re-run every week,
  - Claude vs Grok difference is tracked,
  - results go into a weekly report.

## Decisions in short
- Judges run **only after green CI**. Broken PRs are not paid for, and endpoint coverage stays a separate required check.
- For fork PRs, **foreign code is never executed with secrets**. Code is read as text only via the GitHub API.
- **Combining models** (once Grok is on too):
  - scores are averaged,
  - a hard finding stands when both models raise it, or one does with confidence ≥ 0.8,
  - a **critical security finding from one model is enough** (strict by default; Simecekk can override),
  - a difference ≥ 25 points gets label `vv:judge-disagree`.

## Open questions
1. **`dailyDecayPercent` and `minHolderScore`:** CTO decides. Suggested 1–3 % and 40.
2. **`requireMaintainerApproval`:** suggest `true` for the first few weeks, then `false`.
3. **Turning Grok on:** once there is agreement data with Claude.
4. **Exact models and prices:** CTO picks; verify prices on the providers' pricing pages.

---

# Appendix — Technical spec (for the CTO)

## A1. Architecture
```
PR event ─► judge.yml (pull_request_target, no checkout of PR code)
             │ waits for CI success on head SHA (or is triggered by workflow_run of ci.yml)
             ├─ build input (GitHub API: diff, files at head, description, current area on main, rules.md)
             ├─ for each enabled model × 4 judges: adapter.judge(prompt, input) → JSON  (parallel)
             ├─ validate against judge-verdict.schema.json#/$defs/modelOutput
             ├─ combine → combined-verdict; write audit records to judge-log branch
             ├─ sticky PR comment + labels
             └─ dispatch decide (per area)
decide.yml (concurrency: area-<id>) ─► read state, compare, merge/approve, write data/territories.json (CAS)
sweeper (cron */30) ─► re-dispatch decide for areas with pending candidates; detect stale verdicts
```
- **Provider adapter (day 1):** `JudgeAdapter.judge(system: str, user: str, params) -> RawResult{text, model_version, usage, latency}`. Implementations: `AnthropicAdapter` (`ANTHROPIC_API_KEY`) and `XaiAdapter` (`XAI_API_KEY`). The registry is driven by `gameConfig.judgeModels[]` (`id`, `provider`, `model`, `enabled`). Adding a provider means one adapter class plus one config entry. The core never imports provider SDKs directly.
- **Params:** `temperature: 0`, fixed `maxOutputTokens` (800), JSON mode / structured output where the provider supports it, and a seed where supported. The model id is pinned to an exact version, never an alias.
- **Parsing:** strict JSON parse, then schema validation. If that fails, retry once with a "return only valid JSON" reminder (`parseStatus: repaired`). If it fails again, `parseStatus: failed` and the model verdict is `error`.

## A2. Triggers & CI integration
- **`judge.yml`:**
  - triggers: `pull_request_target: [opened, synchronize, edited, reopened, labeled]` and `workflow_run: {workflows: [ci], types: [completed]}`,
  - it ignores PRs without a valid `[<id>]` title,
  - `edited` re-judges only if the title/body hash changed,
  - `labeled` reacts only to `vv:judge-rejudge`, `vv:judge-override`, `vv:blocked`.
- **Order:** CI (pytest + endpoint coverage, a required check) runs first. The judge runs **only when CI is `success` for the current head SHA**. Pending → exit (`workflow_run` will fire later). Failure → the combined status is `ineligible` with reason `ci_failed`, and no model call is made.
- **Dedup key:** `(headSha, judgeSetHash, descriptionHash)`. An existing combined verdict for that key is reused.
- **Re-judging:** a new push, a changed description, a `vv:judge-rejudge` label, or a `judgeSetHash` change. Each new verdict gets a new `scoredAt`.
- The decision step always reads the **latest combined verdict for the current head SHA**. An older-SHA verdict is never used.

## A3. Security (fork PRs)
- `pull_request_target` and `workflow_run` run with base-repo secrets, so **never check out or execute PR code** in them. There is no `actions/checkout` of the head ref and no pip install from the PR.
- PR content is read via the REST API (`pulls/{n}/files`, `contents?ref=<headSha>`) **as text only**.
- `permissions:` are minimal: `contents: read`, `pull-requests: write`, `issues: write`. Merging and state commits use a GitHub App token, used only in `decide.yml`.
- `ANTHROPIC_API_KEY` and `XAI_API_KEY` live in an environment `judges` that is available only to the judge job, never to `ci.yml` (which runs fork code under `pull_request` without secrets).
- **LLM output is untrusted.** It is schema-validated, only numbers, flags and length-capped strings are used, and the comment is rendered with escaping (no raw markdown/HTML from the model, and links are stripped).
- **Prompt injection:**
  - inputs are wrapped in `<untrusted name=…>` tags,
  - any literal `</untrusted` inside the content is neutralized (e.g. `<\/untrusted`),
  - the preamble instructs the model to ignore embedded instructions,
  - `injectionSuspected` → label `vv:judge-injection` for maintainer review (no automatic penalty),
  - models get no tools or browsing.

## A4. Input building & truncation
- **Always included:**
  - the rules ([RULES.md](../RULES.md)),
  - the context (area id, kind, the endpoints list from CI's coverage report artifact),
  - the file list with +/- stats,
  - the description (capped at 4,000 chars).
- **Priority** under `judgeMaxInputChars` (default 120,000 chars per call; the system prompt is outside the budget):
  1. area code at head,
  2. area tests at head,
  3. `current_area` on main (takeover only),
  4. diff hunks.
- **Per file:** at most 20,000 chars (head 70 % + tail 30 % with a `…[truncated N chars]…` marker). Generated, binary and lock files are omitted.
- **Size limits:**
  - over the budget → `truncation.truncated: true`, and the prompt tells the model to cap confidence at 0.6,
  - area content over `maxAreaChars` (400,000) → `ineligible: area_too_large`, with no model call.
- The input text is byte-for-byte reproducible from refs, and `inputHash` = sha256 of the exact user message.

## A5. Combining
1. Per judge and model, take the parsed `output.score`. Per judge, `score` = the mean over successful models.
2. **Disagreement:** `disagree` is true when `|a−b| ≥ judgeDisagreeDelta` (25) or the hard flags differ. Any disagreement → `vv:judge-disagree`. It is informational only; the maintainer can override or block.
3. **Hard gates:**
   - `matchesArea` / `notCosmetic` fail if all models flag it, or one model flags it with confidence ≥ `judgeHardFailConfidence` (0.8),
   - `securityCritical` fails if **any** model flags it,
   - `judgeFloor` fails if any combined judge score < `judgeFloorScore` (30).
4. **`total`** = Σ `judgeWeights[j]` × `score[j]`, rounded half-up to 1 decimal (decimal arithmetic). The weights must sum to 1, and the config loader asserts this.
5. **`isNewFeature`:**
   - always true for `new-area` and `claim-free`,
   - for a takeover, true only if all successful functionality verdicts say true.
6. **Missing models:**
   - if any judge has zero successful models after 2 retries with backoff → `status: error`, label `vv:judge-error`, and the PR can't take anything until it is re-judged,
   - if one of two models fails, the other model's results are used and the comment says so.
7. **`vv:judge-override`** (maintainer only; the label event actor is checked): the judge gates are treated as `pass` and `status: override`. The CI gate still applies.

## A6. Decide step (takeover, concurrency, decay, novelty)
- **Serialization:** `concurrency: {group: area-<id>, cancel-in-progress: false}`. GitHub keeps only one pending run per group, so **each run processes all candidates of the area, not just the triggering PR**. A cancelled pending run loses nothing, and the sweeper (`*/30`) is the safety net.
- **Candidates:** open PRs for the area with a latest combined verdict that has `status ∈ {scored, override}`, all gates passing, the current `judgeSetHash`, no `vv:blocked`, `ciStatus: success`, mergeable, and the author within `maxOpenPrsPerPlayer`.
- **Ranking:** `total` desc → valid 👍 desc → `scoredAt` asc → PR number asc. Valid 👍 are read via the API at decision time, using the voter rules in [RULES.md](../RULES.md).
- **Decision** (`t` = `decidedAt`, the run start, recorded):
  - `holderEff(t) = max(minHolderScore, holderBaseScore × (1 − dailyDecayPercent/100)^floor((t − holderSince)/1 day))`. When `dailyDecayPercent` is `null`, there is no decay. It is computed on the fly with no cron, and the integer days come from UTC timestamps, so it is deterministic.
  - **owned area:** the best candidate wins if `total > holderEff(t) + takeoverMargin` (strict).
  - **free seed area:** the winner needs `total ≥ minScoreFreeArea`.
  - **new id:** the winner needs `total ≥ minScoreNewArea`.
- **Apply:**
  1. Squash-merge, or label `vv:ready-to-merge` when `requireMaintainerApproval`.
  2. Set the owner to the author: `holderSince = mergedAt`, `holderBaseScore = total + bonus`, `holderJudgeSetHash`, `previousOwner`. The `bonus` = `noveltyBonus` if `isNewFeature` and the author is not in `territory.noveltyAwardedTo`; the author is then added to it.
  3. Append an `ownershipEvents` entry and a `decisions` record (all candidates, `holderEff`, margin, bonus).
- **Remaining candidates** are re-evaluated **in the same run** against the new holder: they must beat `holderEff` of the new holder + margin. After a takeover the other PRs usually conflict, so the bot comments "rebase needed", and a push re-judges them.
- **CAS:** `territory.stateVersion` is read at the start, and the state commit to `main` uses the expected version (fail if changed: refetch and recompute). Merge and state write happen in one run. If the merge fails (a conflict), there is no state change and the bot comments.
- **Re-baseline** on a `judgeSetHash` change:
  - The `rebaseline.yml` job sets `gameConfig.takeoversPaused = true` and re-judges each holder's **current area snapshot on main** (kind `takeover`, empty `current_area`) plus all open candidate PRs.
  - It updates `holderBaseScore = newTotal + bonusPreviouslyApplied`, keeps `holderSince`, then unpauses.
- **Reverts:** handled as in [RULES.md](../RULES.md) A6. A restored previous owner gets their old base score and `holderSince` back.

## A7. Audit log
- **Location:**
  - the orphan branch `judge-log` (bot commits, retried on non-fast-forward): `judge-log/<pr>/<headSha>/<judge>-<modelId>.json` (schema `judge-verdict.schema.json#/$defs/modelVerdict`) and `combined.json` (`#/$defs/combinedVerdict`),
  - the decisions are also in `data/territories.json`,
  - each run also uploads them as a workflow artifact (90 days),
  - the sticky PR comment links to the files.
- **Every record contains:**
  - the model id and exact model version, the prompt version and `promptHash`,
  - `judgeSetHash`, `inputHash` and input refs (base/head SHA, files, description hash, rules hash),
  - params (temperature 0), the raw output, parse status, the parsed output,
  - timestamps, tokens and latency,
  - `costUsd` (filled from a config price table maintained by the CTO; null if empty).
- The log is never rewritten. A correction is a new record.

## A8. Consistency checks
- **Weekly `judge-audit.yml`:** re-runs 10 % of the past week's model verdicts (min 5) with identical input, then computes the mean |Δscore| and the hard-flag flip rate per judge. It alerts in an issue if Δ > 8 or flips > 10 %.
- **Claude vs Grok** (when both are enabled): per judge, the mean absolute difference, the flag agreement rate, and the share of `vv:judge-disagree`.
- Reports go to `judge-log/reports/<yyyy>-W<ww>.json`.
- A **golden set** of ~10 curated PR snapshots, with expected score ranges, is run before any prompt version bump.

## A9. Cost (rough, no prices)
- **Calls per judging** = 4 judges × enabled models (4 with Claude only, 8 with both). Judging happens per push (after green CI) and on description edits.
- **Tokens per call:**
  - input ≈ 1.5k preamble + judge prompt, ≈ 3k rules, plus area content and diff (typically 2–20k), so roughly 6–30k input tokens,
  - output ≈ 150–600 tokens.
- **Monthly** ≈ PR pushes × 4 × models × (input + output). Multiply by the current per-token prices from the providers' pricing pages; **verify current prices before launch**.
- **Mitigations:**
  - prompt caching of the static prefix (preamble + rules),
  - dedup by SHA,
  - running only after green CI,
  - the `maxAreaChars` limit,
  - an optional `judgeMonthlyCallBudget` (the sweeper stops judging when it's exceeded and labels `vv:judge-error`).
