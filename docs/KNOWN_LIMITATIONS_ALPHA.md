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

- **PDF / DOCX export** — use optional libraries (`reportlab` / `python-docx`).
  These are now listed in `requirements.txt`, so a normal install supports them;
  the app still degrades gracefully (a readable "install …" message) if a given
  environment lacks them, and other formats always work.
- **FDX export** — the menu FDX is standard XML; the advanced render-document FDX
  path is experimental.
- **HTML export** — preview-grade.
- **HTTP API LAN / remote modes** — experimental; alpha targets desktop/localhost.
- **Go McKee** plugin and **Connector write actions** — **off by default**.
- **Local voice-to-script (MVP)** — **off by default** (`enable_voice_mode`;
  `voice_backend_mode` defaults to `"disabled"`). Local-first **near-live segmented
  dictation** with manual plain-text commit, in two backend modes: **Local PC**
  (faster-whisper on this computer; local model path, no auto-download) and
  **Local LAN Server** (mic capture stays local; finalized segments go only to a
  Whisper server the user configured on the **trusted local network** — private/
  loopback addresses enforced by default, public URLs / ngrok / cloud tunnels
  **blocked**, redirects refused, no discovery/scanning; see
  `docs/LOCAL_LAN_WHISPER.md`). **No cloud speech API, no OpenAI Realtime.** The
  microphone (`sounddevice`) and Whisper (`faster-whisper`) backends are
  **optional, lazy** installs. With the flag on but the backend missing/
  misconfigured, the panel shows a non-blocking setup message and the app stays
  usable. **Deferred:** cloud realtime / speech-to-speech, automatic
  dialogue/action/note classification, Fountain auto-formatting, voice commands,
  speaker diarization, Live Writer Room, and any ComfyUI/visual link. The panel
  is a **floating, modeless, resizable Voice Dictation window** parented to the
  main window (one instance; toggled show/hide via the menu action /
  Ctrl+Shift+V; close/Hide/Esc hide it with the transcript preview preserved;
  hiding while recording stops the session safely; never a parentless
  top-level window, never auto-shown, never auto-recording). **Phase 2 commit
  targets (conservative, mode-aware):** after review the user picks a *Send
  to* target — cursor insert, New Note, PSYKE draft entry (user-chosen type,
  default **Other**, never auto-classified), Screenplay Action / Dialogue and
  Stage Direction / Dialogue (character chosen manually, never guessed), and
  Graphic Novel Panel fields for the **selected** Panel (appends; "Select a
  Panel first." otherwise). Listing never mutates; commits are blocked if the
  project changed since transcription; the project goes dirty only after a
  successful commit. **Deferred:** Outline / Series-episode draft items
  ("Outline voice target not available yet.") and Append-to-Manuscript (the
  open editor owns the scene body — use cursor insert). **Phase 3 transcript
  history (local, session-only):** segments can be edited (original kept),
  selected and committed together (visible order, edited text, via the
  router), merged/split, retried on the locally-held audio (in-memory only,
  dropped on discard/clear — "Audio segment no longer available." after),
  discarded/cleared, and the **last** voice commit can be undone where safe
  (editor revision guard / GN previous value / created Note-PSYKE deletion —
  otherwise disabled with the reason). History does not persist across app
  restarts. **Phase 4 Intent mode (opt-in, preview-first):** a transcript can
  be treated as an *instruction* from a fixed allowlist — rule-based cleanup
  (no AI, never fabricates), insert-cleaned via the commit targets, AI
  rewrite-of-selection and AI summarize-to-Note (existing provider settings
  only, text-only — audio never goes to AI; disabled with a clear message
  when no provider is configured), PSYKE draft (user-chosen type) and GN
  Panel-field send. Every intent previews before/after and applies only on
  explicit confirm; stale previews (project/target/before-text drift) are
  blocked; applied intents are covered by the same Undo. **Phase 5 Billy
  Voice Bridge:** selected transcript segments can be sent to Billy (the
  Assistant) as a question or editing instruction — **text + minimal safe
  context only, never audio, never secrets**, via the existing provider
  configuration (all Billy actions disable with a clear message when no
  provider is set). Proposals (chat answer, rewrite-selection,
  continue-from-cursor, Note draft, PSYKE draft with user-chosen type, GN
  Panel-field update with mirror) are preview-first with explicit
  Apply/Cancel, stale-proposal blocking and the shared Undo; dangerous
  spoken "commands" are refused chat-only without reaching the provider.
  **Phase 6 Voice Room (Alpha shell):** one local review-first session
  workflow — explicit crash-proof state machine, a context summary line, a
  session-scoped proposal queue (draft/ready/applied/cancelled/stale/failed;
  stale can never apply; double-click re-activates a ready item) and four
  explicit workflow modes (Dictation default / Intent / Ask Billy / Edit
  with Billy — never auto-detected), plus Pause that keeps session, history
  and queue. **Still not:** full Live Writer Room, voice-to-voice
  conversation, a continuous autonomous agent loop, automatic mode
  detection, automatic command execution, automatic screenplay role
  guessing, automatic PSYKE classification, speaker diarization, or an
  image-generation bridge; no shell/system commands; cloud realtime remains
  deferred. See `docs/VOICE_MVP.md`.

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
- **Series now has a real Season → Episode → Act → Chapter → Scene hierarchy
  (Phase 1 foundation).** Seasons and Episodes are **stored rows**; each Series
  scene links to its Episode via `Scene.episode_id`; the Act→Chapter→Scene outline
  is **episode-scoped** (scene-derived, filtered by `episode_id`). The **Series
  Navigator** is the canonical structural surface for this — create / rename /
  delete / move Seasons, Episodes, internal Acts/Chapters and Scenes, and move a
  scene between Episodes. Deleting a Season/Episode **unlinks** its scenes (it
  never deletes a body). Phase-1 boundary: the **global** Outline / Manuscript /
  Timeline are still **episode-agnostic** (they read the canonical flat
  Act→Chapter→Scene); Season/Episode-aware *global* Outline context-switching is a
  later phase. Series Season/Arc and Episode beat plans remain settings-backed and
  **name-keyed** (consistent with `act_summaries` / `chapter_summaries`); the
  Navigator looks A/B/C buckets up by Episode title.
- **Legacy Series projects keep working and can convert.** A Series project that
  pre-dates the hierarchy (Act/Chapter used as Season/Episode, no Season rows)
  renders in the original **read-only** Navigator view and offers a one-click,
  **confirmed Convert to Season/Episode** migration. The migration is
  **non-destructive**: old Act → Season title, old Chapter → Episode title, scenes
  linked by `episode_id`; bodies, labels and order are untouched (so the global
  Outline is unchanged).
- **Persistent relation links are reported, not persisted.** Cross-scene /
  cross-episode setup-payoff, cliffhanger/reveal, A/B/C thread, and character-arc
  links are **detected and reported**, but not yet stored as durable links.
  Per-scene A/B/C thread assignment is likewise not yet stored.
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
- **Series Navigator** is a Series-only item under the left **Plan** group and is
  now the **structural editor** for the Season → Episode → Act → Chapter → Scene
  hierarchy (see the Series hierarchy note above). For projects with real Season
  rows it offers full CRUD and moves; for legacy projects it stays read-only with a
  confirmed convert action. **A/B/C Plots** remain read-only buckets derived from
  the Episode Beat Plan's `a/b/c_story` fields (no per-scene thread assignment
  metadata yet). Navigation: a scene opens in the Manuscript; structural nodes open
  the (global, flat) Outline. **Phase-1 operation scope** (deferred, not bugs):
  Season create/rename/delete/move and Episode create/rename/delete/move *within a
  season*, internal Act/Chapter create/rename, Scene create/rename/delete/move and
  **moving a scene between Episodes** are supported; **moving a whole Episode to a
  different Season** and **reordering internal Acts/Chapters** (only Scenes reorder)
  are deferred. The "episode-local outline" is the Navigator's Episode subtree
  itself; a dedicated Season/Episode-aware *global* Outline panel is deferred (the
  global Outline stays flat — see the Series hierarchy note). The full Season →
  Episode → Act → Chapter → Scene **path is available** (`series_structure.
  scene_series_path`); wiring it into the Manuscript title bar is deferred.
- **Graphic Novel — Pages/Panels managed in the Outline + Manuscript (standalone
  Pages section disabled).** The separate left-panel **Pages** route was fullscreen-
  hostile (clicking it minimized the app in macOS fullscreen, across multiple
  attempted fixes), so it is **disabled for Alpha**: hidden in every mode, route
  inert (never mounts the old standalone Pages widget). Graphic Novel Page/Panel
  navigation now lives in **two mirrored surfaces** over the shared `Scene.content`
  body:
  - the **Outline** (`GraphicNovelOutlineView`) is the GN Page/Panel navigator —
    a **Scenes** tab (`Act → Chapter → Scene → Page → Panel`, editable) and a
    **Pages** tab (a chapter-level cross-reference grouping panels across the
    chapter's scenes by page number, so a page can show panels from more than one
    scene), with a selected-Panel editor (**Visual / Caption / Dialogue / SFX /
    Notes**), add / move / delete, assign-panel-to-page, and double-click → Manuscript;
    Pages are renamed via the page detail (title field). **Panel** reorder (within a
    scene) and **move-panel-to-page** are supported; **Page reorder** (move Page
    up/down) is deferred for Alpha (pages are scene-scoped and authored in order).
  - the **Manuscript** (`GraphicNovelManuscriptView`) is the **comics script
    editor** (Superscript-style): the scene flows as a script document — PAGE
    headings, then **one large free-typing script block per panel** where the
    writer types labeled sections (**Visual / Caption / Dialogue / SFX /
    Notes** — labels optional, unlabeled text is the Visual, speaker lines
    like `NAME: …` stay content). Blocks parse back into the canonical
    five-field model on commit (focus-out); line breaks inside a field are
    preserved end-to-end; page/panel numbers stay auto-numbered. Per-page
    **+ Panel** / **Delete Page**, per-panel move / delete (confirmed). It is
    **not** a tree/outliner and **not** a form: scene selection is a flat
    dropdown, structure stays in the Outline (double-clicking a Panel there
    focuses its script block here).
  Both read/write the **same** `Scene.content` (single source of truth — no separate
  Pages storage), so edits mirror. Relationships: **Chapter owns Pages** (via its
  scenes), **Scene owns Panels**, **Panel is assigned to a Page** (its containing
  page), and a **Scene can span multiple Pages**. **Storage note (Alpha):** pages are
  physically **scene-scoped** (each scene owns its Pages/Panels in its body); the
  chapter Page View surfaces panels from multiple scenes by page number, but
  physically merging panels from different scenes onto one shared page record is a
  documented future step. Both surfaces are single embedded **child widgets** (no
  separate route, no top-level window, no dialog on mount), so they cannot trigger
  the fullscreen minimize. This structure is the intended **future anchor point for
  visual-production integrations** (panel visual brief / render status / generated
  assets); **no image generation / prompt / ComfyUI** fields exist today. (Confirm in
  macOS fullscreen — smoke-test F-items — that opening the GN Outline/Manuscript does
  not minimize the app.)
- **Graphic Novel — one shared body.** The Manuscript edits the GN scene body
  (`Scene.content`, structured by `graphic_novel_blocks` into Pages → Panels:
  visual / caption / dialogue / SFX / notes). Pages/Panels are **writing/script
  structure, not image generation** — no ComfyUI, no image prompts, no visual
  canvas in the editing path. For completeness: a standalone image-*prompt* export
  module (`graphic_novel_ai_export`) and a "Prompt" action on the deprecated legacy
  pages view still exist in the codebase — they emit **text** prompt sheets only,
  and the **ComfyUI connector is a disabled stub** (`comfyui_available()` is
  `False`; `send_to_comfyui` raises). **No image generation runs**, and no
  image/ComfyUI action exists in the Logos/Assistant registry.
