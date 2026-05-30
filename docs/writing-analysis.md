# Writing-Quality Analysis

Logosforge ships a suite of **deterministic craft analyzers** that read your prose
and structure and surface issues — clarity, rhythm, voice, energy, grammar,
pacing, balance, and health. They are pure and run with **no network calls**;
several can *optionally* blend in an LLM score on a background thread, but every
one produces a useful result offline. Many render as colour-coded underlines and a
margin "energy gutter" directly in the manuscript editor.

> Source: `storyplanner/style_analysis.py`, `voice_consistency.py`,
> `voice_learner.py`, `grammar_checker.py`, `paragraph_energy.py`,
> `dialogue_attribution.py`, `pacing_insights.py`, `character_balance.py`,
> `story_health.py`, `analytics.py`, `narrative_suggestions.py`, and the editor
> integration in `ui/writing_core_view.py` + `ui/manuscript_highlighter.py`.

---

## Style analysis

`style_analysis.py` scores a paragraph on five metrics (0–1): **clarity**
(penalizes long sentences, long words, subordinate-clause density, repetition),
**concision** (filler words, weak verbs, preposition/adverb density),
**rhythm** (sentence-length variation — flags both monotony and chaos),
**tone consistency** (formal/casual/neutral shifts), and **dialogue naturalness**
(when dialogue is present). It also emits inline **style hints** (long sentences,
word repetition, uniform rhythm, stiff dialogue) as character-range underlines,
with low/medium/high **sensitivity** levels controlling how many fire. PSYKE
character state can boost the metrics (stress → rhythm, formality → tone), and an
optional `StyleRefineWorker` blends an LLM score in. The module also generates
actionable suggestions and a heuristic filler-trimming rewrite.

---

## Voice consistency & the voice learner

A `VoiceProfile` (per character) captures **tone**, **sentence length**,
**vocabulary level**, **punctuation style**, **quirks**, and **dialogue markers**.

- **Voice learner** (`voice_learner.py`) infers a profile from a character's
  dialogue: it measures average sentence length, contraction rate (→ casual vs
  formal), elevated/simple vocabulary, punctuation frequencies, quirks (contraction
  avoidance, frequent trailing off, exclamatory speech), and leading dialogue
  markers ("Well…", "Look…"), with a confidence score that grows with sample size.
  `learn_voice_profile()` merges inferred traits into the stored profile while
  respecting any user-locked fields. It can also generate voice-faithful rewrites
  and adjust a profile for a character's current emotional state.
- **Voice consistency** (`voice_consistency.py`) compares each dialogue line
  against its speaker's profile and flags **deviations** (e.g. "too formal for this
  character") with a score and up to two reasons, at low/medium/high sensitivity.
  Deviations render as a distinct dash underline in the editor.

---

## Grammar checker

`grammar_checker.py` is a **custom, rule-based** checker (not an external service).
It auto-detects language by trigram frequency (en/es/fr/de/pt/it) and reports
three issue kinds: **spelling** (English, via a common-word list plus
morphological suffix rules; capitalized words and possessives are ignored),
**grammar** (doubled words, sentence-start capitalization), and **style**
(passive voice, over-long sentences). Each issue carries a position range, a
message, and up to four suggestions. Spelling and grammar render as wave
underlines; style as a dot underline. The grammar language can be forced from the
Edit menu (Auto / English / Italian / Spanish / French / German).

---

## Paragraph energy & the energy gutter

`paragraph_energy.py` scores each paragraph on **tension**, **pacing**,
**conflict**, and **emotional shift** (from danger/conflict/emotion keyword
densities, sentence brevity, dialogue ratio, and emotional-valence deltas). It
detects **flow hints** across a sequence — flat sections, pacing spikes/drops, and
emotionless runs. PSYKE story context boosts the scores, and an optional
`EnergyRefineWorker` blends an LLM score in.

In the editor this becomes the **energy gutter**: a thin left-margin strip with a
per-paragraph dot coloured by tension (green → red) and a diamond marker where a
flow hint applies, with a hover tooltip breaking down tension/pacing/conflict. It
recomputes on a short debounce after edits.

---

## Other analyzers

| Analyzer | Module | What it does |
|----------|--------|--------------|
| **Dialogue attribution** | `dialogue_attribution.py` | Maps quoted lines to speakers using speech-tag, proximity, and turn-taking heuristics (feeds voice analysis). |
| **Pacing insights** | `pacing_insights.py` | Up to five scene-level issues: character disappearance, monotony (same plotline/cast runs), middle stagnation, arc neglect, character clustering. |
| **Character balance** | `character_balance.py` | Flags **dominant** and **underused** characters and **thin** arcs by scene presence and act spread. |
| **Story health** | `story_health.py` | Four rolled-up signals — Structure (metadata completeness), Characters (distribution evenness), Arc coverage (arcs spanning the story), Density (scene length) — each scored balanced / sparse / problematic. |
| **Analytics** | `analytics.py` | Word/paragraph/sentence counts, dialogue ratio, and project aggregates (avg/longest/shortest). |
| **Narrative suggestions** | `narrative_suggestions.py` | Builds the "Suggest Beats" request — five grounded next-beat directions (Escalation, Reversal, Delay, Internal Shift, Reveal). |

These surface in dedicated sidebar views (Health, Balance, Pacing, Arcs) and feed
the Dashboard, the Adaptive mode, and the AI context.

---

## Unified underlines in the editor

The manuscript editor combines the analyzers into a single, non-overlapping
underline layer (`ui/writing_core_view.py`, applied via Qt `ExtraSelection`s),
priced by priority so they never collide:

1. **Grammar** — spelling/grammar as wave underlines, style as a dot underline.
2. **Voice deviations** — dash underline (skipped where it would overlap grammar).
3. **Style hints** — dot underline (skipped where it would overlap grammar or
   voice).

All carry hover tooltips (grammar adds inline suggestions), are cached per
paragraph for performance, and recompute on debounced edits. Layered on top are the
PSYKE entity highlighting (see [psyke.md](psyke.md)), the energy gutter, and the
[Auto-Link](auto_link.md) and [Context Assistant](context_assistant.md) banners —
together giving continuous, glanceable feedback without interrupting the writing.

---

## Related deterministic systems

These analyzers share a design philosophy with the other read-only intelligence
layers documented separately:

- [structural_intelligence.md](structural_intelligence.md) — seven PSYKE-driven
  structural detectors.
- [narrative_dashboard.md](narrative_dashboard.md) — the four-panel visual story
  dashboard.
- [context_assistant.md](context_assistant.md) — proactive, rate-limited writing
  hints.
- [auto_link.md](auto_link.md) — suggest-only manuscript↔PSYKE linking.
