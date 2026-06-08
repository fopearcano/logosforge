# Alpha Release Candidate — Checklist

Companion to [ALPHA_RC_STATUS.md](ALPHA_RC_STATUS.md),
[ALPHA_TEST_COMMANDS.md](ALPHA_TEST_COMMANDS.md), and the broader
[ALPHA_RELEASE_CHECKLIST.md](ALPHA_RELEASE_CHECKLIST.md) (private-alpha closure).
This file is the **multi-mode RC** checklist used before tagging.

## Pre-release (hard gate)

- [x] Branch is `claude/setup-storyplanner-app-5cVxF`; working tree clean.
- [x] Version is `0.9.0-alpha` (`storyplanner/__init__.py`).
- [x] Alpha Release Gate audit = **A** ([ALPHA_RELEASE_GATE_AUDIT.md](ALPHA_RELEASE_GATE_AUDIT.md)).
- [x] Per-mode integrity audits = **A** (Screenplay / Graphic Novel / Stage Script / Series).
- [x] No production code changed during packaging.
- [ ] Manual smoke test completed (below).
- [ ] Maintainer sign-off to tag (tagging is a separate, explicit step).

## Automated tests

- [x] Focused gate — `pytest tests/test_alpha_release_gate.py` → **35 passed**.
- [x] Broad certification sweep → **1527 passed, 0 failures** (see
      [ALPHA_TEST_COMMANDS.md](ALPHA_TEST_COMMANDS.md)).
- [x] Per-mode phase suites green (Screenplay 1–10, Graphic Novel 1–8, Stage
      Script 1–8, Series 1–8).
- [x] Cross-cutting green (structure invariant, project + PSYKE isolation,
      manuscript/outline separation, timeline, notes, logos).

## Manual smoke test

1. [ ] Launch the app (`python3 run.py`).
2. [ ] Create a new project.
3. [ ] Create **Act → Chapter → Scene** in the Outline.
4. [ ] Switch writing mode through all five — **Novel, Screenplay, Graphic Novel,
       Stage Script, Series** — one at a time.
5. [ ] Verify the **Manuscript** editor behavior changes per mode (prose vs.
       screenplay blocks vs. page/panel vs. stage blocks vs. teleplay blocks) in
       the **same** Manuscript section.
6. [ ] Verify **Outline** still shows the canonical Act → Chapter → Scene structure.
7. [ ] Verify **Timeline** opens and lanes are independent (not Acts/Seasons).
8. [ ] Verify **Notes** and **PSYKE** are project-bound.
9. [ ] Verify the **Logos** quick-actions dropdown is readable (not a tiny button row).
10. [ ] Verify changing the **theme** updates Assistant/Logos live.
11. [ ] Edit body text → confirm the project shows a **dirty** marker.
12. [ ] Close the app → confirm a **save prompt** appears for the modified project.
13. [ ] Reopen → confirm data **persists**.
14. [ ] **Export** one project/body (Markdown/Text/Fountain).
15. [ ] Confirm the export contains **no API keys / provider secrets**.
16. [ ] Switch projects → confirm **no data leakage** between projects.

## Project isolation

- [ ] Project A data (blocks, plans, Timeline, Notes, PSYKE, dashboards, export)
      not visible in Project B.
- [ ] Switching B → A returns A's data intact.
- [ ] A brand-new Project C has no A/B debris.

## Export / privacy

Exports and reports must **not** include: API keys, provider settings, Assistant
configuration secrets, unrelated/previous-project data, sentinel strings, system
prompts, debug markers, ComfyUI / image-generation settings, or production-
scheduling data. (Automated coverage in `tests/test_alpha_release_gate.py` and the
per-mode export tests.)

- [ ] Spot-check one exported file for the above.

## Dirty-state / save

- [ ] Creating/editing Manuscript/Outline/Timeline/Notes marks the project dirty.
- [ ] Preview-only operations (health/reflection/continuity/dashboard, rewrite
      preview, plan preview) do **not** mutate or mark dirty before apply.
- [ ] Cancel leaves data and dirty state unchanged.
- [ ] Project switch / close prompts to save when dirty.

## Theme / UI

- [ ] Sidebar routes to the correct sections; Manuscript mounts the correct mode
      editor; Outline/Timeline/Notes/PSYKE/Assistant mount correctly.
- [ ] Theme change propagates live to Assistant and the Logos toolbar.
- [ ] Usable at small window width; no obsolete "Classical" header / extra
      Navigator panel; Manuscript summary/navigation rail intact.

## Deferred features (must remain off/hidden)

- [ ] **Canvas Plot** hidden from navigation.
- [ ] No **ComfyUI / image-generation** module, action, or settings.
- [ ] No **production scheduling / rehearsal / writers-room** management.
- [ ] No **showrunner automation** that mutates data.
- [ ] No separate **Season/Episode** storage hierarchy (Series stays
      Act → Chapter → Scene internally).
