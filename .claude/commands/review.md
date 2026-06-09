---
description: Multi-expert review of a branch, spec, or plan — adapts lenses to docs vs code, then lists or implements fixes
argument-hint: [branch | spec <path> | plan <path> | <PR-number>] [--focus "..."] [--list | --fix]
---

You are running a multi-expert review. Unlike a fixed branch review, the **target and the focus
are chosen by the user**, and there is **no report file** — you (main Claude) synthesize the
findings in chat and then either **list** them or **implement the fixes**, depending on what the
user wants.

# 1. Decide what to review, how to focus, and what to do with the findings

Parse `$ARGUMENTS`:

- **Target** (what gets reviewed):
  - *empty* or `branch` → the current branch vs the default branch. Diff = `git diff <base>...HEAD`
    + `git diff` (working tree) + `git status --porcelain`. Resolve `<base>` as `origin/HEAD`'s
    branch (fallback `main`, then `master`). Capture the branch via `git rev-parse --abbrev-ref HEAD`.
  - `spec [<path>]` → review a spec. If no path, find the newest under
    `docs/superpowers/specs/`; if several plausible, ask which.
  - `plan [<path>]` → review an implementation plan (e.g. under `docs/plans/` or
    `docs/superpowers/plans/`). Same path-resolution rule.
  - a bare **number** → PR mode: `gh pr diff <n>` for the diff, `gh pr view <n> --json
    headRefName,baseRefName,title` for metadata. *(If `gh` is unavailable in this environment, use
    the GitHub MCP `pull_request_read` tools instead.)* Per-target generalists that need head-branch
    files are skipped in PR mode unless the PR is checked out locally.
- **Focus** (`--focus "…"`): an optional lens to emphasize (e.g. "architecture / future-proofing",
  "implementation-readiness", "security"). If present, every agent must weight it heavily and you
  add a dedicated focus lens. If absent, run the default lens set for the detected content type.
- **Action** (`--list` | `--fix`): what to do after synthesis. If neither is given, **ask the user**
  once: *list the findings only, or implement the fixes?* (Offer "list" as the safe default.)

If the target is ambiguous after parsing (e.g. empty args on a docs-only repo with no branch diff),
**ask the user** what to review before dispatching anything.

# 2. Gather the material and detect content type

- Pull the diff / read the target file(s) per the chosen target.
- **Detect content type of the changed/target material:**
  - **Code** — any top-level service dir (one holding a build entrypoint: `main.go`, `package.json`,
    `pyproject.toml`, `Cargo.toml`, …) or shared lib dirs whose files appear in scope. Build
    `TOUCHED_UNITS`.
  - **Docs/design** — Markdown specs, ADRs (`docs/decisions/`), plans, architecture docs.
- Read any repo conventions file first if it exists (`CLAUDE.md`, `CONTRIBUTING.md`, an
  `ARCHITECTURE.md`, the ADR log) — findings must be judged against the project's own stated rules,
  not generic preference.
- If there is genuinely nothing reviewable (no diff, no target file), say so and stop.

# 3. Dispatch the expert lenses (parallel — one message, all Agent calls together)

Pick the lens set from the detected content type. Each agent returns **≤ 600 words**, every
finding tagged `critical` / `high` / `medium` / `low` / `nitpick` with **`file:line` evidence**, and
**proposes a concrete fix** for each finding (so the optional fix phase has something to act on).

## If the material is DOCS / DESIGN (specs, ADRs, plans)

Dispatch these lenses over the target docs (+ the ADR log / ARCHITECTURE for context):

1. **Architecture & design coherence** — do the decisions fit together, is the topology sound, are
   responsibilities cleanly bounded, any decision that undercuts another.
2. **Completeness & internal consistency** — contradictions across sections/ADRs, dangling
   references, stale numbers after edits, open items that are actually resolved (or vice-versa),
   unversioned/under-specified contracts.
3. **Future-proofing & extensibility** — will this extend by configuration not rewrite, are the
   seams in the right places, any premature abstraction or painted-in corner.
4. **Feasibility & risk** — anything technically dubious, under-budgeted, or that won't survive
   contact with reality (licensing, rate limits, hardware, timelines); honest-ceiling gaps.
5. **Clarity & implementation-readiness** — could a fresh engineer/agent build from this without
   guessing; ambiguities that could be read two ways; missing acceptance criteria / contracts.
6. *(+ a dedicated **Focus lens** if `--focus` was given.)*

## If the material is CODE

*(In PR mode, skip the per-unit generalists unless the PR is checked out locally — they need the
head-branch files, per §1.)* Dispatch **N per-unit generalists** (one per `TOUCHED_UNITS` member) — each reads the unit's
conventions doc, its entry/handler/store files, and the scoped diff, judging: diff correctness vs
local conventions; scope drift / cohesion; abstraction churn (justified? still earning keep?);
design fit; **project-pattern adherence** (whatever the repo's `CLAUDE.md`/conventions mandate);
and any repo-specific hard rules (e.g. a doc that must change in lockstep). Plus these **global
lenses** over the full diff:

1. **Language/idiom expert** — idioms, error handling, naming, types, conventions-doc compliance.
2. **Test-automation** — new exported code has matching tests in the same diff (else `high` — TDD
   violation); error-path coverage; table-driven structure; mock staleness (regenerate and check);
   `-race`. Revert any generated diff after checking.
3. **Bug & security finder** — correctness bugs, races, injection, leaked secrets, unsafe defaults,
   swallowed errors, missing boundary validation. Run the repo's SAST target if one exists and
   surface medium+ as `critical`/`high`.
4. **Performance** — hot-path allocations, N+1 queries, goroutine/connection leaks, blocking calls
   in handlers, missing batching/pagination/caching, sync-primitive choice.
5. **Observability** — structured logging, request-ID/context propagation, tracing/metrics on new
   paths, no logging of secrets or full payloads.
6. *(+ a dedicated **Focus lens** if `--focus` was given.)*

# 4. Synthesize in chat — NO report file

Do **not** write a report file and do **not** commit anything in this phase. In your own message,
present:

1. **Header** — target (branch/spec/plan/PR + name), base/context, content type, focus (if any).
2. **Findings by lens** — each lens's findings, severity-tagged, with `file:line` evidence and the
   proposed fix. Collapse duplicate findings across lenses; note agreement.
3. **Prioritized action list** — the top 5–10 across all lenses, ordered by severity then
   impact ÷ effort. Each: severity, action, `file:line`, why.
4. **Counts** — critical / high / medium / low / nitpick, and a one-line risk read.

# 5. List or implement the fixes

- **`--list`** (or the user chose "list") → stop after the synthesis above. Offer to implement.
- **`--fix`** (or the user chose "implement") → apply the fixes yourself, smallest-blast-radius
  first, skipping any finding that conflicts with a stated project decision (call those out instead
  of silently applying). Group related edits, keep changes faithful to existing conventions, and
  when done print a concise summary of what you changed and what you deliberately left. **Do not
  commit or push unless the user asks** — leave the working tree for them to inspect, consistent
  with this repo's "commit only when asked" rule.

Keep the final chat output tight: the synthesis, then (if fixing) the change summary. No filler.
