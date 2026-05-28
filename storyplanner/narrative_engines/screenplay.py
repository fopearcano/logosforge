"""Screenplay narrative engine — film / TV screenplay reasoning."""

from __future__ import annotations

from storyplanner.narrative_engines.base import NarrativeEngine


SCREENPLAY_ENGINE = NarrativeEngine(
    name="screenplay",
    label="Screenplay",
    description="Visual, temporal, performative, production-aware storytelling. "
                "Scenes are the unit; pacing is measured in screen time; "
                "subtext, blocking and setup/payoff are first-class concerns.",
    structural_units=("act", "sequence", "scene", "beat"),
    plot_block_unit="scene",
    timeline_semantics="screen_time",
    assistant_priorities=(
        "visual action",
        "cinematic pacing",
        "scene duration",
        "blocking",
        "subtext",
        "setup/payoff",
        "dialogue economy",
        "continuity",
    ),
    assistant_terminology={
        "block": "scene",
        "unit": "beat",
        "chapter": "sequence",
    },
    psyke_context_rules=(
        "subtext state",
        "character knowledge state",
        "continuity",
        "visual motifs",
    ),
    review_checks=(
        "scene turns",
        "dialogue economy",
        "visual conflict",
        "duration",
        "setup/payoff",
        "blocking clarity",
    ),
    default_format="screenplay",
    compatible_formats=("screenplay", "series"),
)
