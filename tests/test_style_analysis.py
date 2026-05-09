"""Tests for style_analysis — ParagraphStyle model and metric computation."""

from unittest.mock import patch

from storyplanner.style_analysis import (
    ParagraphStyle,
    _parse_style_metrics,
    analyze_paragraph,
    analyze_paragraphs,
    analyze_style,
    clear_cache,
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


# -- analyze_style (cached API) ------------------------------------------------

def test_analyze_style_returns_paragraph_style():
    clear_cache()
    result = analyze_style("The dog ran across the field.")
    assert isinstance(result, ParagraphStyle)
    assert "clarity" in result.metrics


def test_analyze_style_cache_hit():
    clear_cache()
    text = "The fox jumped over the lazy dog."
    first = analyze_style(text)
    second = analyze_style(text)
    assert first is second


def test_analyze_style_different_texts_not_cached():
    clear_cache()
    a = analyze_style("Hello world.")
    b = analyze_style("Goodbye world.")
    assert a is not b


def test_cache_cleared_by_clear_cache():
    clear_cache()
    text = "Cached paragraph text."
    first = analyze_style(text)
    clear_cache()
    second = analyze_style(text)
    assert first is not second


def test_cache_eviction_at_max():
    clear_cache()
    for i in range(520):
        analyze_style(f"Paragraph number {i} unique text here.")
    from storyplanner.style_analysis import _style_cache
    assert len(_style_cache) <= 512


# -- Different texts produce different metrics ---------------------------------

def test_different_texts_different_clarity():
    clear_cache()
    clear_text = "She ran. He jumped. They stopped."
    muddy_text = (
        "The individual who was previously situated adjacent to the "
        "antiquated door which had been constructed approximately "
        "forty-seven years previously although the precise date remained "
        "somewhat uncertain among the various inhabitants."
    )
    a = analyze_style(clear_text)
    b = analyze_style(muddy_text)
    assert a.metrics["clarity"] > b.metrics["clarity"]


def test_different_texts_different_concision():
    clear_cache()
    tight = "He sprinted across the field."
    wordy = (
        "He was very really quite basically just honestly totally "
        "completely absolutely definitely running across the field."
    )
    a = analyze_style(tight)
    b = analyze_style(wordy)
    assert a.metrics["concision"] > b.metrics["concision"]


def test_different_texts_different_rhythm():
    clear_cache()
    uniform = (
        "The dog ran fast. The cat sat down. The man went home. "
        "The bird flew up. The sun went down."
    )
    varied = (
        "She stopped. The long winding road stretched out before her, "
        "disappearing into mist. She breathed. Then she walked on."
    )
    a = analyze_style(varied)
    b = analyze_style(uniform)
    assert a.metrics["rhythm"] > b.metrics["rhythm"]


# -- Repeated words → lower clarity -------------------------------------------

def test_repeated_words_lower_clarity():
    clean = "The cat sat on the mat. She looked out the window."
    repetitive = (
        "The castle stood on the castle hill. The castle walls "
        "surrounded the castle grounds near the castle gate."
    )
    a = analyze_paragraph(0, clean)
    b = analyze_paragraph(0, repetitive)
    assert a.metrics["clarity"] > b.metrics["clarity"]


def test_repeated_word_note():
    text = (
        "The castle stood on the castle hill. The castle walls "
        "surrounded the castle grounds near the castle gate."
    )
    result = analyze_paragraph(0, text)
    assert any("repeat" in n.lower() for n in result.notes)


# -- Adverb detection ---------------------------------------------------------

def test_excessive_adverbs_lower_concision():
    clean = "He walked to the door and opened it."
    adverby = (
        "He extremely quickly walked to the incredibly enormous door "
        "and very slowly, deeply, completely opened it."
    )
    a = analyze_paragraph(0, clean)
    b = analyze_paragraph(0, adverby)
    assert a.metrics["concision"] > b.metrics["concision"]


def test_adverb_note():
    text = (
        "She very slowly and extremely carefully and incredibly "
        "thoroughly and deeply completely examined the room."
    )
    result = analyze_paragraph(0, text)
    assert any("adverb" in n.lower() for n in result.notes)


# -- Dialogue punctuation -----------------------------------------------------

def test_dialogue_excessive_exclamation():
    normal = '"Hey," she said. "What happened?"'
    loud = '"Hey!!! What!!! Is!!! Going!!!! On!!!!" she screamed.'
    a = analyze_paragraph(0, normal)
    b = analyze_paragraph(0, loud)
    dn_a = a.metrics.get("dialogue_naturalness", 1.0)
    dn_b = b.metrics.get("dialogue_naturalness", 1.0)
    assert dn_a >= dn_b


def test_dialogue_semicolons_lower_naturalness():
    natural = '"I think we should go," he said.'
    stilted = '"I think; however, we should consider; perhaps, going," he said.'
    a = analyze_paragraph(0, natural)
    b = analyze_paragraph(0, stilted)
    dn_a = a.metrics.get("dialogue_naturalness", 1.0)
    dn_b = b.metrics.get("dialogue_naturalness", 1.0)
    assert dn_a > dn_b


# -- Long sentences → lower concision -----------------------------------------

def test_long_sentences_lower_concision():
    short = "He sat. She stood. The door opened."
    long_sent = (
        "The man who was standing by the ancient and weathered door which "
        "had been built many decades ago opened it with a slow and careful "
        "motion of his hand while glancing nervously over his shoulder at "
        "the crowd that had gathered behind him in the narrow hallway."
    )
    a = analyze_paragraph(0, short)
    b = analyze_paragraph(0, long_sent)
    assert a.metrics["concision"] > b.metrics["concision"]


# -- LLM metric parsing -------------------------------------------------------

def test_parse_style_metrics_valid():
    raw = '{"clarity": 0.8, "concision": 0.7, "rhythm": 0.9, "tone_consistency": 0.85}'
    result = _parse_style_metrics(raw)
    assert result is not None
    assert result["clarity"] == 0.8
    assert result["rhythm"] == 0.9


def test_parse_style_metrics_with_dialogue():
    raw = '{"clarity": 0.8, "concision": 0.7, "rhythm": 0.9, "tone_consistency": 0.85, "dialogue_naturalness": 0.6}'
    result = _parse_style_metrics(raw)
    assert result is not None
    assert "dialogue_naturalness" in result


def test_parse_style_metrics_clamps():
    raw = '{"clarity": 1.5, "concision": -0.3, "rhythm": 0.5, "tone_consistency": 0.8}'
    result = _parse_style_metrics(raw)
    assert result["clarity"] == 1.0
    assert result["concision"] == 0.0


def test_parse_style_metrics_missing_keys():
    raw = '{"clarity": 0.8, "concision": 0.7}'
    result = _parse_style_metrics(raw)
    assert result is None


def test_parse_style_metrics_invalid_json():
    assert _parse_style_metrics("not json") is None


def test_parse_style_metrics_empty():
    assert _parse_style_metrics("") is None


def test_parse_style_metrics_with_surrounding_text():
    raw = 'Here are the metrics: {"clarity": 0.9, "concision": 0.8, "rhythm": 0.7, "tone_consistency": 0.6} done.'
    result = _parse_style_metrics(raw)
    assert result is not None
    assert result["clarity"] == 0.9


# -- StyleRefineWorker ---------------------------------------------------------

def test_refine_worker_exists():
    from storyplanner.style_analysis import StyleRefineWorker
    assert StyleRefineWorker is not None


def test_refine_worker_blends_on_success():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    from storyplanner.style_analysis import StyleRefineWorker

    heuristic = ParagraphStyle(
        paragraph_id=0,
        metrics={"clarity": 0.4, "concision": 0.6, "rhythm": 0.8, "tone_consistency": 0.5},
    )
    llm_response = '{"clarity": 0.8, "concision": 0.4, "rhythm": 0.6, "tone_consistency": 0.9}'

    results = []

    def mock_chat(messages, **kwargs):
        return llm_response, False

    worker = StyleRefineWorker(heuristic, "some text")
    worker.completed.connect(results.append)

    with patch("storyplanner.assistant.chat_completion", mock_chat), \
         patch("storyplanner.style_analysis._build_provider"):
        worker.run()

    assert len(results) == 1
    blended = results[0]
    assert blended.metrics["clarity"] == round(0.4 * 0.4 + 0.8 * 0.6, 3)
    assert blended.metrics["concision"] == round(0.6 * 0.4 + 0.4 * 0.6, 3)


def test_refine_worker_emits_failed_on_bad_response():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    from storyplanner.style_analysis import StyleRefineWorker

    heuristic = ParagraphStyle(
        paragraph_id=0,
        metrics={"clarity": 0.5, "concision": 0.5, "rhythm": 0.5, "tone_consistency": 0.5},
    )

    errors = []

    def mock_chat(messages, **kwargs):
        return "I can't do that.", False

    worker = StyleRefineWorker(heuristic, "text")
    worker.failed.connect(errors.append)

    with patch("storyplanner.assistant.chat_completion", mock_chat), \
         patch("storyplanner.style_analysis._build_provider"):
        worker.run()

    assert len(errors) == 1


def test_refine_worker_emits_failed_on_exception():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    from storyplanner.style_analysis import StyleRefineWorker

    heuristic = ParagraphStyle(
        paragraph_id=0,
        metrics={"clarity": 0.5, "concision": 0.5, "rhythm": 0.5, "tone_consistency": 0.5},
    )

    errors = []

    def mock_chat(messages, **kwargs):
        raise ConnectionError("no server")

    worker = StyleRefineWorker(heuristic, "text")
    worker.failed.connect(errors.append)

    with patch("storyplanner.assistant.chat_completion", mock_chat), \
         patch("storyplanner.style_analysis._build_provider"):
        worker.run()

    assert len(errors) == 1
    assert "no server" in errors[0]
