# QUANTUM Outliner

The **QUANTUM Outliner** is Logosforge's branch-exploration engine. It treats a
narrative decision point as a **superposition** of possible continuations, scores
each one along several independent dimensions, lets you compare them, and then
**collapses** the one you choose into canon — applying its consequences to PSYKE
and archiving the roads not taken.

The quantum vocabulary is a metaphor, not physics. It gives writers an intuitive
mental model for narrative uncertainty and branching.

> Source: the `storyplanner/quantum_outliner/` package. UI in
> `storyplanner/ui/quantum_timeline.py`. The structure-method knowledge base it
> retrieves from lives in [`docs/Writing-Methods_RAG.md`](Writing-Methods_RAG.md).

---

## The metaphor

| Term | Meaning in Logosforge |
|------|------------------------|
| **Wavefunction** | A set of 3–5 possible next moves anchored to one story situation. |
| **Branch** | One candidate continuation, with a title, description, stakes, consequence, and a *state delta* (how it changes characters/relations/arcs). |
| **Superposition** | All branches of a wavefunction held live at once, each with a probability. |
| **Collapse** | Choosing one branch — it becomes canon, its state delta is applied to PSYKE, and the rest are archived. |
| **Uncertainty** | Weak/under-developed scenes worth re-exploring. |
| **Relativity** | Re-reading the same moment from a different character's point of view. |

Two outline modes exist: **CLASSICAL** (a stable, linear beat path derived from a
writing method) and **LAMBDA** (full branching superposition with collapse).

---

## What it does, end to end

1. **Generate** — you describe a situation (or a premise for a fresh outline) and
   the engine produces 3–5 structurally and emotionally distinct branches
   (`possibilities.py`). Generation can be QUANTUM (free exploration), CLASSICAL
   (anchored to retrieved story beats), HYBRID (first branch on-structure, the rest
   exploratory), or AUTO. If no LLM is available it falls back to offline stub
   branches so the UI is never blank.
2. **Score** — every branch is evaluated on five factors and ranked (`scoring.py`,
   below).
3. **Compare & explain** — branches can be shown side by side (A/B/C) with factor
   deltas, trade-off chips ("↑ tension", "↓ novelty"), and plain-language
   explanations of why each scores as it does.
4. **Collapse** — you pick a branch. `collapse.py` applies its state delta to PSYKE
   via `psyke_adapter.apply_collapse()` (append character notes, connect relations,
   update arcs), records the choice in the decision log, archives the wavefunction,
   and offers follow-up proposals (create the next scene, add a consequence note,
   add progressions).

---

## The scoring model

Each branch is scored 0–1 on five independent factors (`scoring.py`):

| Factor | What it measures |
|--------|------------------|
| **structure_fit** | Adherence to the current beat/method. |
| **psyke_consistency** | Consistency with established characters, relations, and arcs. |
| **tension_gain** | Emotional intensity (conflict/danger/sacrifice/loss signals). |
| **novelty** | Freshness relative to its sibling branches. |
| **goal_alignment** | How well it advances the protagonist's stated goal. |

The factors are blended with **weights**. Five presets ship — *Balanced*,
*Conservative*, *Bold*, *Character-driven*, *Plot-driven* — and weights are
editable live (the scoring-weights popover). Weights are further shaped by:

- **Beat-phase bias** — at *setup* structure matters more; at *catalyst* novelty
  is boosted; at *climax* tension dominates. The engine maps the current beat to a
  phase and applies per-phase multipliers.
- **Online adaptation** — when you collapse a branch, weights nudge slightly toward
  the factors that branch scored highly on (optional learning).

Raw scores become **probabilities** via softmax. Branches that violate a **hard
constraint** (e.g. "no death", parsed into forbidden keywords) are zeroed out.

### Goals, look-ahead, and Pareto

Beyond the five-factor blend, the outliner supports **goal-driven optimization**
(`QuantumGoals`): objective weights (tension, consistency, novelty, structure,
character focus), minimum-factor constraints, and a 1–3 step **look-ahead** that
lightly simulates future branching to estimate a move's longer-term value
(cached and depth/breadth-capped in `lookahead_cache.py`). Goal presets include
*Balanced, High Tension, Character-first, Experimental*.

For multi-objective thinking, it computes a **Pareto front** — the set of branches
that aren't dominated on every objective — so you can see genuinely different
"best" options rather than a single winner. Selection mode can be **weighted**
(by probability) or **pareto**.

### Heuristic + optional LLM (ensemble)

Factor scores are computed by fast heuristics, and can be **blended** with scores
from an LLM evaluator (`llm_evaluator.py`) via a configurable ensemble weight. As
everywhere in Logosforge, the LLM is optional: without it, the heuristics stand
alone.

---

## Uncertainty & Relativity

- **Uncertainty** (`uncertainty.py`) scans the manuscript for weak scenes — short,
  tension-free, filler-heavy, dialogue-less — and surfaces them as candidates to
  re-explore (the `detect_weak_scenes` entry point).
- **Relativity** (`relativity.py`) re-renders a scene from another character's
  point of view (protagonist / antagonist / named character / neutral), returning
  how the events read, what they mean, and what shifts from that frame.

---

## The Quantum Timeline UI

`ui/quantum_timeline.py` visualizes canon and live branches in parallel:

- one column per scene (plus an "unlinked" column),
- in CLASSICAL mode each scene shows its title and beat marker; in LAMBDA mode it
  also shows an uncertainty marker (⟨ψ⟩ N paths) and the **branch lanes**,
- each branch is a card with its probability (as a coloured bar), beat, branch type
  (deviation / alternative / intensification / resolution), stakes, consequence,
  factor chips, an optional Pareto badge, and a status badge (active ○, selected ◉,
  collapsed ●, archived ◌),
- left-click selects a branch; right-click offers **collapse** (with confirm) or
  **archive**; a popover edits the scoring weights.

---

## Persistence

Live quantum state is held in memory per project (`state.py`) and serialized to the
`QuantumStateRecord` row (`persistence.py`, one row per project), so branches and
selections survive restarts and travel with the project on export/import.
Collapsed wavefunctions are archived as JSON under
`~/.storyplanner/quantum/archive_<project_id>.json`, and each collapse appends to
the project's **decision log** (`Database.append_decision`), which the
*"decision history"* view replays.

Per-project quantum configuration — scoring weights, preset, constraints, goals,
ensemble alpha, show-tradeoffs, selection mode — is stored in the project's
settings (`Database` quantum accessors).

---

## Writing-Methods RAG

CLASSICAL and HYBRID generation ground their beats in a small retrieval knowledge
base of story-structure methods (`writing_methods_rag.py`) sourced from
[`docs/Writing-Methods_RAG.md`](Writing-Methods_RAG.md): Save the Cat, Hero's
Journey, Three-Act, Kishōtenketsu, Seven-Point, Story Circle, Snowflake,
Scene-Sequel, Fichtean Curve, Story Spine, MICE Quotient, Try-Fail Cycles,
Promises & Payoffs, and Negative Space. A keyword query returns the most relevant
methods and their beat lists, which are folded into the generation prompt and the
`structure_fit` scoring. **Editing that markdown file changes what the outliner
knows** — it is a genuine, editable knowledge base.
