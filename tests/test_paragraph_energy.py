"""Tests for ParagraphEnergy — per-paragraph writing dynamics."""

import time

from storyplanner.paragraph_energy import (
    ParagraphEnergy,
    analyze_scene_energy,
    compute_paragraph_energy,
)


# -- Model creation ------------------------------------------------------------

def test_model_defaults():
    e = ParagraphEnergy(paragraph_id=0, scene_id=1)
    assert e.paragraph_id == 0
    assert e.scene_id == 1
    assert e.metrics == {}
    assert e.last_updated > 0


def test_model_with_metrics():
    m = {"tension": 0.5, "pacing": 0.7, "conflict": 0.3, "emotional_shift": 0.1}
    e = ParagraphEnergy(paragraph_id=2, scene_id=5, metrics=m)
    assert e.metrics == m


def test_model_properties():
    m = {"tension": 0.4, "pacing": 0.6, "conflict": 0.2, "emotional_shift": 0.8}
    e = ParagraphEnergy(paragraph_id=0, scene_id=1, metrics=m)
    assert e.tension == 0.4
    assert e.pacing == 0.6
    assert e.conflict == 0.2
    assert e.emotional_shift == 0.8


def test_model_properties_default_zero():
    e = ParagraphEnergy(paragraph_id=0, scene_id=1)
    assert e.tension == 0.0
    assert e.pacing == 0.0
    assert e.conflict == 0.0
    assert e.emotional_shift == 0.0


def test_last_updated_auto():
    before = time.time()
    e = ParagraphEnergy(paragraph_id=0, scene_id=1)
    after = time.time()
    assert before <= e.last_updated <= after


def test_last_updated_explicit():
    e = ParagraphEnergy(paragraph_id=0, scene_id=1, last_updated=12345.0)
    assert e.last_updated == 12345.0


# -- Compute single paragraph --------------------------------------------------

def test_compute_empty_text():
    e = compute_paragraph_energy(0, 1, "")
    assert e.tension == 0.0
    assert e.conflict == 0.0
    assert e.emotional_shift == 0.0


def test_compute_calm_paragraph():
    text = "The sun set over the quiet village. Birds sang in the trees."
    e = compute_paragraph_energy(0, 1, text)
    assert 0.0 <= e.tension <= 0.3
    assert 0.0 <= e.conflict <= 0.2


def test_compute_tense_paragraph():
    text = (
        "She feared the darkness that lurked in every shadow. "
        "Danger loomed. She trembled, dreading what crept behind her."
    )
    e = compute_paragraph_energy(0, 1, text)
    assert e.tension > 0.3


def test_compute_conflict_paragraph():
    text = (
        "They fought and argued. He attacked and she refused to back down. "
        "The enemy confronted them with rage and fury."
    )
    e = compute_paragraph_energy(0, 1, text)
    assert e.conflict > 0.3


def test_compute_fast_pacing():
    text = "He ran. She jumped. They fled. Explosions crashed around them!"
    e = compute_paragraph_energy(0, 1, text)
    assert e.pacing > 0.5


def test_compute_slow_pacing():
    text = (
        "The long and winding road stretched endlessly through the vast, "
        "rolling countryside, where ancient trees swayed gently in the "
        "warm afternoon breeze that carried the scent of wildflowers "
        "across the meadows and into the distant hills beyond."
    )
    e = compute_paragraph_energy(0, 1, text)
    assert e.pacing < 0.6


def test_compute_emotional_shift():
    text = "She laughed with joy. Then she sobbed, overwhelmed by grief."
    e = compute_paragraph_energy(0, 1, text)
    assert e.emotional_shift > 0.3


def test_compute_no_emotional_shift():
    text = "The table was wooden. The chair was also wooden."
    e = compute_paragraph_energy(0, 1, text)
    assert e.emotional_shift == 0.0


def test_metrics_in_range():
    text = (
        "He screamed and fought the enemy who lurked in the darkness. "
        "She laughed, then sobbed. They ran, crashed, and fled!"
    )
    e = compute_paragraph_energy(0, 1, text)
    for key in ("tension", "pacing", "conflict", "emotional_shift"):
        assert 0.0 <= e.metrics[key] <= 1.0, f"{key} out of range"


def test_compute_returns_all_four_metrics():
    e = compute_paragraph_energy(0, 1, "Hello world.")
    assert set(e.metrics.keys()) == {"tension", "pacing", "conflict", "emotional_shift"}


def test_compute_preserves_ids():
    e = compute_paragraph_energy(3, 7, "Some text.")
    assert e.paragraph_id == 3
    assert e.scene_id == 7


# -- Analyze scene energy (attach to paragraphs) ------------------------------

def test_analyze_scene_empty():
    result = analyze_scene_energy(1, "")
    assert result == []


def test_analyze_scene_single_paragraph():
    result = analyze_scene_energy(1, "A single paragraph of text.")
    assert len(result) == 1
    assert result[0].paragraph_id == 0
    assert result[0].scene_id == 1


def test_analyze_scene_multiple_paragraphs():
    content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    result = analyze_scene_energy(1, content)
    assert len(result) == 3
    for i, e in enumerate(result):
        assert e.paragraph_id == i
        assert e.scene_id == 1


def test_analyze_scene_blank_lines_skipped():
    content = "Para one.\n\n\n\nPara two."
    result = analyze_scene_energy(1, content)
    assert len(result) == 2


def test_analyze_scene_preserves_scene_id():
    result = analyze_scene_energy(42, "Some content.\nMore content.")
    for e in result:
        assert e.scene_id == 42


def test_analyze_scene_sequential_ids():
    content = "A.\nB.\nC.\nD."
    result = analyze_scene_energy(1, content)
    assert [e.paragraph_id for e in result] == [0, 1, 2, 3]


def test_analyze_scene_each_has_metrics():
    content = "First line.\nSecond line."
    result = analyze_scene_energy(1, content)
    for e in result:
        assert "tension" in e.metrics
        assert "pacing" in e.metrics
        assert "conflict" in e.metrics
        assert "emotional_shift" in e.metrics
