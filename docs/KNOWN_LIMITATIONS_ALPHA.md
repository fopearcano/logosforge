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

## Writing-mode systems (multi-mode Alpha RC)

The five writing modes (Novel / Screenplay / Graphic Novel / Stage Script /
Series) ship on one **universal Manuscript** + `writing_mode` adapter. Mode-system
limitations for this RC:

- **Heuristic, rule-based checks.** Mode health, reflection, continuity, and
  dashboard signals are conservative string / marker / overlap heuristics (no
  NLP) — directional craft guidance, not authoritative. A/B/C-story support and
  season-arc alignment use word overlap, so paraphrased material can read as
  unsupported.
- **Dashboards refresh on open + manual button.** The Screenplay / Graphic Novel
  / Stage Script / Series Review Dashboards recompute when opened or via Refresh
  (no live debounced recompute). "Open in Manuscript" focuses the scene (block-
  level deep-linking is the scene scroll today).
- **Series still uses Act → Chapter → Scene internally.** "Season / Arc" and
  "Episode" are **display labels** over canonical Acts/Chapters. Series Season/Arc
  and Episode beat plans are settings-backed and **name-keyed** to Acts/Chapters
  (consistent with `act_summaries` / `chapter_summaries`); renaming or duplicate
  names across acts can desync a plan.
- **Persistent relation links are reported, not persisted.** Cross-scene /
  cross-episode setup-payoff, cliffhanger/reveal, A/B/C thread, and character-arc
  links are **detected and reported**, but not yet stored as durable links.
- **No real Season/Episode storage migration.** The Series writing system never
  uses the legacy `Season`/`Episode` tables; a dedicated Season/Episode storage
  hierarchy is deferred.
- **Out of scope (deferred), confirmed absent:** ComfyUI / image generation,
  Canvas Plot (hidden from navigation), production scheduling, rehearsal / writers-
  room management, and showrunner automation that mutates data. "Showrunner" and
  "Writers-Room" exist only as an AI prompt persona and a reflection perspective
  label.
- **Mode-aware AI is propose-then-confirm.** Every mutating Assistant/Logos action
  goes through a preview and a confirmed Controlled Apply (STAGE checkpoint); there
  is no silent overwrite. Deterministic checks never call the provider.
- **Writing mode is locked after a project has meaningful content.** Mode is chosen
  at project creation; once the project contains body text, planning data,
  Timeline/Notes/PSYKE, or user-created structure, the Project Settings mode
  selector is disabled and any mode change is refused (no mutation). This prevents
  accidental body/parser misinterpretation (e.g. prose read as screenplay blocks).
  **Mode conversion is deferred** to a future explicit "Convert Project Mode"
  workflow — it does **not** exist yet. To work in a different mode today, create a
  new project. (The project's *default writing format* for new scenes remains
  editable; it does not reinterpret existing bodies.)
