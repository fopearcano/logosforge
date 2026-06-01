# Known Limitations (Alpha 0.9.0-alpha)

Honest list of what is **incomplete, experimental, or deferred** in the private
alpha. Nothing here is a data-safety risk; it's about scope and polish. See
[ALPHA_SCOPE.md](ALPHA_SCOPE.md) for the full scope statement.

## Deferred to beta (services exist, UI not yet)

These work as **services + Logos/Assistant surfaces**, but have **no dedicated UI
panel** yet:

- **Knowledge Graph** — built/queried via Logos + Assistant context; the
  multi-mode graph UI is deferred. ([NarrativeKnowledgeGraph.md](NarrativeKnowledgeGraph.md))
- **Semantic Continuity** — checks run via Logos/Assistant; no panel yet.
  ([SemanticContinuityEngine.md](SemanticContinuityEngine.md))
- **Decision Radar / Project Intelligence** — available as data + Logos actions;
  Radar UI deferred. ([DecisionRadar.md](DecisionRadar.md))
- **Guided Workflows** — engine + Logos + Assistant context; no workflow panel.
  ([GuidedWorkflows.md](GuidedWorkflows.md))

## Experimental / optional

- **PDF / DOCX export** — need optional libraries (`reportlab` / `python-docx`).
  Without them you get a readable message; other formats work.
- **FDX export** — the menu FDX is standard XML; the advanced render-document FDX
  path is experimental.
- **HTML export** — preview-grade.
- **HTTP API LAN / remote modes** — experimental; alpha targets desktop/localhost.
- **Go McKee** plugin and **Connector write actions** — **off by default**.

## Model / feature limits

- **Plot** and **Timeline** are derived from scene fields, not standalone models
  (no event dates / rich plot graph yet).
- **Continuity** flags only evidence-backed, deterministic issues; deep-NLP checks
  (voice drift, knowledge leak, object reuse, lore-rule violation) are not done.
- **Knowledge Graph** centrality is plain degree; undefined-term detection is
  heuristic.
- **Grammar / spelling** is a basic rule-based checker (no external engine).
- **Fountain** block classification is heuristic; dual-dialogue and title-page
  metadata are minimal (no text is lost — unknown lines become action).

## Platform / scope

- **Single-user, local-only.** No cloud sync, no collaboration (cloud folders are
  treated as ordinary local paths).
- All projects share one local SQLite database; per-project JSON exports /
  snapshots are your isolated backups.
- **Restore** loads a snapshot as a *new* project (non-destructive) rather than
  reverting the current project in place.
- API keys are stored in plaintext in the local settings file (never exported or
  logged).

## Beta blockers (before scope expands)

1. Record a full-suite-green baseline after each closing change.
2. UI panels for the deferred intelligence services.
3. API LAN/remote hardening + required auth before non-desktop exposure.
4. Richer Plot/Timeline models; opt-in semantic continuity checks.

## Not a bug

- A **"Segoe UI" font warning** off-Windows is harmless (font fallback applies).
- **PDF/DOCX "Export failed: install …"** when the optional lib isn't present.
- The **Assistant panel auto-hiding** on a narrow window (it protects the editor
  width).
