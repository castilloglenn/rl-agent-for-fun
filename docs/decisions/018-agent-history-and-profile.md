# 018: Agent history, profile, and the first milestone

**Date:** 2026-09-27. **Status:** Implemented in roadmap step 5a6 (`src/agents/history.py`, `src/experiments/agents.py`, `make agents`, `make agent`).

## Context

An agent's story was scattered: checkpoints in its folder, scores in `evaluations/`, and phases in run folders. Reviewing it (for you, or for Claude) meant opening several files. The roadmap planned layered storage: a small profile first, an event history next, and per-episode detail only in run folders.

## Decision

- **`agents/<id>/history.jsonl`: events, not episodes.** Appended, never rewritten. Events: `created` (also for a branch, with `branched_from`), `phase_started`, `phase_resumed`, `checkpoint_saved`, `scored`, `new_best`, `milestone`, `phase_ended`, and `episodes` (a summary per 100 training episodes: mean, min, max score, wreck rate). About 180 bytes per event (measured).
- **`agents/<id>/profile.json`: the digest (about 1 KB),** rebuilt from the history and the files on disk after each event: model, lineage (each phase's trainer, reward, stage, rules, decisions, status), totals, newest and best checkpoints with the best one's suite scores, and the milestone.
- **Repeated events:** a Ctrl+C can repeat an event after resume. The profile keeps the latest of each. History writes never touch training, so exact resume holds.
- **The milestone, "first skilled agent":** the best checkpoint on the suite wrecks in under half the rounds and beats the heuristic's mean round score on the same seeds. It's checked whenever a checkpoint is scored, and recorded once. The heuristic's scores are cached in `agents/baselines/<suite>-v<version>.json` per code version.
- **Commands:** `make agents` (one line per agent) and `make agent AGENT=id` (lineage, best scores next to the heuristic, a score trend over the scored checkpoints, totals, milestone).
- **No checkpoint pruning yet.** Measured: a checkpoint is 50 KB, and a 2M-decision phase writes about 1.1 MB. The roadmap's retention policy waits until agents grow much larger.
- **No backfill:** agents from before 5a6 start their history at their next event (alpha: retrain instead).

## Consequences

- Reviewing an agent starts from one ~1 KB file.
- The cached heuristic score follows the code version, and a tree with uncommitted changes shares one version ("-dirty"). After a physics change, delete `agents/baselines/` (or commit) to refresh it.
