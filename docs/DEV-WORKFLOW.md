# Development Workflow & "Superpowers" (deferred)

This project will eventually be built using a disciplined, skill-driven development
workflow (the "superpowers" set of practices). **We are intentionally deferring that
machinery until the implementation phase** — right now we are still in research and
strategy/brainstorming, where heavy process adds no value.

## What we're deferring (and will adopt when coding starts)
- **Brainstorming-before-building** — explore intent/requirements/design before writing code.
- **Writing plans** — turn the agreed design into a written, step-by-step implementation plan.
- **Test-driven development** — write the failing test first, then the implementation.
- **Systematic debugging** — root-cause before fixing.
- **Worktrees / isolation** — isolated workspaces per feature.
- **Parallel & subagent-driven development** — fan out independent tasks.
- **Code review + verification-before-completion** — evidence before claiming "done".
- **Finishing-a-branch** — structured merge/PR/cleanup.

## Why deferred
The fundamentals (is this clickable? will it earn? what are the real risks?) must be settled
before we invest in build process. We're using `superpowers:brainstorming` now for the
whole-idea assessment; the rest of the workflow activates at milestone **M0** (scaffold).

## When it activates
At the start of implementation (M0 in DESIGN.md milestones): plan → TDD → review → verify,
on the designated feature branch.
