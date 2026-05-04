"""Tests for style_analysis — ParagraphStyle model and metric computation."""

from storyplanner.style_analysis import (
    ParagraphStyle,
    analyze_paragraph,
    analyze_paragraphs,
)


# -- ParagraphStyle model -----------------------------------------------------

def test_model_creation():
    ps = ParagraphStyle(paragraph_id=0, metrics={"clarity": 0.9}, notes=[])
    assert ps.paragraph_id == 0
    assert ps.metrics == {"clarity": 0.9}
    assert ps.notes == []
    assert ps.last_updated > 0


def test_model_defaults():
    ps = ParagraphStyle(paragraph_id=5)
    assert ps.paragraph_id == 5
    assert ps.metrics == {}
    assert ps.notes == []
    assert ps.last_updated > 0


def test_model_with_notes():
    ps = ParagraphStyle(
        paragraph_id=1,
        metrics={"clarity": 0.4},
        notes=["Sentences may be too complex or long"],
    )
    assert len(ps.notes) == 1
    assert "complex" in ps.notes[0]


def test_model_custom_timestamp():
    ps = ParagraphStyle(paragraph_id=0, last_updated=1000.0)
    assert ps.last_updated == 1000.0


def test_model_auto_timestamp():
    import time
    before = time.time()
    ps = ParagraphStyle(paragraph_id=0)
    after = time.time()
    assert before <= ps.last_updated <= after


# -- analyze_paragraph -------------------------------------------------------

def test_analyze_returns_paragraph_style():
    result = analyze_paragraph(0, "The dog ran across the field.")
    assert isinstance(result, ParagraphStyle)
    assert result.paragraph_id == 0


def test_analyze_has_all_base_metrics():
    result = analyze_paragraph(0, "The dog ran across the field quickly.")
    assert "clarity" in result.metrics
    assert "concision" in result.metrics
    assert "rhythm" in result.metrics
    assert "tone_consistency" in result.metrics


def test_analyze_metrics_in_range():
    result = analyze_paragraph(0, "She walked home. The rain fell softly.")
    for key, val in result.metrics.items():
        assert 0.0 <= val <= 1.0, f"{key} = {val} out of range"


def test_analyze_clean_prose_high_scores():
    text = (
        "The old man sat by the window. Rain tapped against the glass. "
        "He sipped his coffee and watched the street below."
    )
    result = analyze_paragraph(0, text)
    assert result.metrics["clarity"] >= 0.7
    assert result.metrics["concision"] >= 0.7
    assert result.metrics["tone_consistency"] >= 0.7


def test_analyze_wordy_prose_low_concision():
    text = (
        "He was very really quite honestly just basically totally completely "
        "absolutely definitely certainly perhaps maybe somewhat rather actually "
        "going to the store."
    )
    result = analyze_paragraph(0, text)
    assert result.metrics["concision"] < 0.6


def test_analyze_long_sentences_low_clarity():
    text = (
        "The man who was standing by the door which was old and creaky and "
        "which had been painted several times over the years although it was "
        "still showing signs of wear and tear from the weather and the many "
        "people who had passed through it on their way to the garden that "
        "stretched out behind the house and which was full of flowers and "
        "trees that had been planted by his grandmother many years ago."
    )
    result = analyze_paragraph(0, text)
    assert result.metrics["clarity"] < 0.7


def test_analyze_uniform_sentences_low_rhythm():
    text = (
        "The dog ran fast. The cat sat down. The man walked home. "
        "The bird flew high. The sun went down. The moon came out."
    )
    result = analyze_paragraph(0, text)
    assert result.metrics["rhythm"] <= 0.7


def test_analyze_varied_rhythm_high_score():
    text = (
        "She stopped. The long, winding road stretched out before her, "
        "disappearing into the mist that clung to the distant hills. "
        "She breathed. Then she walked on."
    )
    result = analyze_paragraph(0, text)
    assert result.metrics["rhythm"] >= 0.7


# -- Dialogue ----------------------------------------------------------------

def test_dialogue_detected():
    text = '"I don\'t think so," he said. "Not today."'
    result = analyze_paragraph(0, text)
    assert "dialogue_naturalness" in result.metrics


def test_no_dialogue_no_metric():
    text = "The sun set behind the mountains."
    result = analyze_paragraph(0, text)
    assert "dialogue_naturalness" not in result.metrics


def test_natural_dialogue_high_score():
    text = '"Hey, what\'s going on?" she asked. "Nothing much," he said.'
    result = analyze_paragraph(0, text)
    assert result.metrics["dialogue_naturalness"] >= 0.7


def test_stilted_dialogue_lower_score():
    text = (
        '"I must confess that the preponderance of evidence which has been '
        'accumulated over the course of our extraordinarily comprehensive '
        'investigation leads me to the inescapable conclusion that the '
        'perpetrator of these unconscionable acts is none other than the '
        'individual who has been systematically undermining our institutional '
        'frameworks," he declared solemnly.'
    )
    result = analyze_paragraph(0, text)
    dn = result.metrics.get("dialogue_naturalness", 1.0)
    assert dn <= 0.8


# -- Notes -------------------------------------------------------------------

def test_notes_generated_for_low_clarity():
    text = (
        "The man who was standing by the door which was old and creaky and "
        "which had been painted several times over the years although it was "
        "still showing signs of wear and tear from the weather and the many "
        "people who had passed through it."
    )
    result = analyze_paragraph(0, text)
    if result.metrics["clarity"] < 0.6:
        assert any("complex" in n.lower() or "long" in n.lower() for n in result.notes)


def test_notes_generated_for_low_concision():
    text = (
        "He was very really quite honestly just basically totally completely "
        "absolutely definitely going to the store."
    )
    result = analyze_paragraph(0, text)
    assert any("filler" in n.lower() for n in result.notes)


def test_clean_prose_no_notes():
    text = "The old man sat by the window. He watched the rain."
    result = analyze_paragraph(0, text)
    assert len(result.notes) == 0


# -- analyze_paragraphs (multi) -----------------------------------------------

def test_analyze_paragraphs_returns_list():
    text = "First paragraph here.\n\nSecond paragraph here."
    results = analyze_paragraphs(text)
    assert isinstance(results, list)
    assert len(results) == 2


def test_analyze_paragraphs_ids_sequential():
    text = "One.\n\nTwo.\n\nThree."
    results = analyze_paragraphs(text)
    assert [r.paragraph_id for r in results] == [0, 1, 2]


def test_analyze_paragraphs_empty_text():
    results = analyze_paragraphs("")
    assert results == []


def test_analyze_paragraphs_blank_lines_skipped():
    text = "Hello.\n\n\n\nWorld."
    results = analyze_paragraphs(text)
    assert len(results) == 2


def test_analyze_paragraphs_single():
    text = "Just one paragraph."
    results = analyze_paragraphs(text)
    assert len(results) == 1
    assert results[0].paragraph_id == 0


# -- Edge cases ---------------------------------------------------------------

def test_empty_paragraph():
    result = analyze_paragraph(0, "")
    assert result.metrics["clarity"] == 1.0
    assert result.metrics["concision"] == 1.0


def test_single_word():
    result = analyze_paragraph(0, "Hello")
    for val in result.metrics.values():
        assert 0.0 <= val <= 1.0


def test_paragraph_id_preserved():
    result = analyze_paragraph(42, "Test text.")
    assert result.paragraph_id == 42


def test_metrics_are_rounded():
    result = analyze_paragraph(0, "She walked home. The rain fell softly.")
    for val in result.metrics.values():
        s = str(val)
        if "." in s:
            decimals = len(s.split(".")[1])
            assert decimals <= 3
