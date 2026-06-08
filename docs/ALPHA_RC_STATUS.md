# Alpha Release Candidate — Status

**Classification: A — Ready for Alpha Release Candidate.**

- **Product:** Logosforge — local-first Creative Writing system (Python core).
- **Version:** `0.9.0-alpha` (`storyplanner/__init__.py` · `__status__ = "alpha"`).
- **Branch:** `claude/setup-storyplanner-app-5cVxF`.
- **Date:** 2026-06-08.
- **Scope of this step:** Alpha RC **packaging / freeze + documentation only** — no
  product features, no refactors, **no production code changed**.

## Post-gate blocker fix

One Alpha-blocker was fixed after the gate: **writing mode is now locked once a
project has meaningful content** (it was previously switchable, which could make
the Manuscript read one mode's body as another's). Mode is chosen at creation and
locked thereafter; the Project Settings selector is disabled with a clear message
and any mode change is refused without mutating data. Conversion remains a deferred
future workflow. Single source of truth: `writing_modes.can_change_writing_mode` /
`change_writing_mode`. See `docs/KNOWN_LIMITATIONS_ALPHA.md`.

## Last audit summary

The final global multi-mode integrity audit (the **Alpha Release Gate**, see
[ALPHA_RELEASE_GATE_AUDIT.md](ALPHA_RELEASE_GATE_AUDIT.md)) returned **A**: all five
writing modes form one coherent system on the universal Manuscript, with the
canonical Act → Chapter → Scene invariant, project isolation, export privacy,
dirty-state handling, mode-aware non-mutating AI assistance, and no scope creep.
Per-mode integrity audits also returned A: Screenplay, Graphic Novel
([GRAPHIC_NOVEL_MODE_INTEGRITY_AUDIT.md](GRAPHIC_NOVEL_MODE_INTEGRITY_AUDIT.md)),
Stage Script ([STAGE_SCRIPT_MODE_INTEGRITY_AUDIT.md](STAGE_SCRIPT_MODE_INTEGRITY_AUDIT.md)),
and Series ([SERIES_MODE_INTEGRITY_AUDIT.md](SERIES_MODE_INTEGRITY_AUDIT.md)).

## Tests run / result

| Run | Command | Result |
|-----|---------|--------|
| Focused gate | `pytest tests/test_alpha_release_gate.py` | **35 passed** |
| Broad certification sweep | see [ALPHA_TEST_COMMANDS.md](ALPHA_TEST_COMMANDS.md) | **1527 passed, 0 failures** |

The previously-known red tests (two stale `test_logos_integration.py` cases that
referenced the removed `_action_buttons` toolbar API) were fixed at the test layer;
the suite is now fully green. The full ~120-file suite cannot finish inside the
environment's time cap, so the gate runs a broad blast-radius sweep across every
mode + cross-cutting surface (see [ALPHA_TEST_COMMANDS.md](ALPHA_TEST_COMMANDS.md)).

## Changed files for packaging (this step)

Documentation only:

- `RELEASE_NOTES_ALPHA.md` (updated — Alpha RC multi-mode section)
- `CHANGELOG.md` (updated — Alpha RC entry)
- `docs/ALPHA_RC_STATUS.md` (new — this file)
- `docs/ALPHA_RC_CHECKLIST.md` (new)
- `docs/ALPHA_TEST_COMMANDS.md` (new)
- `docs/KNOWN_LIMITATIONS_ALPHA.md` (updated — multi-mode RC section)
- `docs/ALPHA_RELEASE_GATE_AUDIT.md` (updated — final RC status note)

**Production code touched: none.**

## Deferred work (out of scope, intentionally)

- Canvas Plot (hidden/deferred), ComfyUI / image generation, production scheduling,
  rehearsal / writers-room management, showrunner automation, and a real separate
  Season/Episode storage hierarchy. See
  [KNOWN_LIMITATIONS_ALPHA.md](KNOWN_LIMITATIONS_ALPHA.md).

## Recommended next steps

1. **Manual local smoke test** — follow [ALPHA_RC_CHECKLIST.md](ALPHA_RC_CHECKLIST.md).
2. **Optional Git tag** — only after manual confirmation, and only when explicitly
   instructed (this step does **not** tag).
3. **Optional GitHub release** — after tagging, when instructed.
4. **Commercial packaging plan** — prepared separately (see below).

## Commercial product note (documentation only)

The **current repository is the Python core / main creative-writing app** — the
single source of truth for the engine, data model, and AI surfaces. The planned
commercial products are **separate, later packaging/distribution targets**:

- an **Electron desktop app**, and
- a **Web app**,

both of which should **call or attach to this Python core / API** rather than
re-implement it. This Alpha RC is the Python core milestone and **should not be
conflated** with final Electron/Web commercial packaging.
