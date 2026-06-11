"""Software UI language — lightweight translation registry (Alpha).

The **Software UI Language** is global and entirely separate from any
project's Writing Language: changing one never changes the other. English is
the default and the complete reference; **Italian** ships as the first
(partial) translation. Coverage is incremental by design — strings are
translated where :func:`tr` is applied (language/settings surfaces first),
everything else stays English. No machine translation of the whole UI, no
Qt ``.qm`` toolchain (a plain in-code catalog keeps Alpha risk low; the
``tr()`` call sites are the extraction points for a future full pass).

Only languages with an actual catalog are selectable, and the Preferences UI
labels the coverage as partial — an unsupported UI language is never shown
as complete.
"""

from __future__ import annotations

# Selectable UI languages: code -> native display label. Only list languages
# that really have a catalog below (English is the built-in reference).
UI_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("it", "Italiano"),
)

DEFAULT_UI_LANGUAGE = "en"

# Per-locale catalogs: exact English source string -> translation.
# Keep entries in sync with the tr() call sites; missing keys fall back to
# English (partial coverage is expected and documented for Alpha).
_CATALOG: dict[str, dict[str, str]] = {
    "it": {
        "Language": "Lingua",
        "Software UI Language:": "Lingua dell'interfaccia:",
        "Default writing language (new projects):":
            "Lingua di scrittura predefinita (nuovi progetti):",
        "Writing Language:": "Lingua di scrittura:",
        "UI translations are partial in Alpha; untranslated text stays "
        "in English. Applies to newly opened windows and dialogs.":
            "Le traduzioni dell'interfaccia sono parziali nella Alpha; il "
            "testo non tradotto resta in inglese. Si applica alle nuove "
            "finestre e finestre di dialogo.",
        "The writing language guides AI, grammar checking and Dexter's "
        "Room. Changing it never rewrites or translates your text.":
            "La lingua di scrittura guida l'AI, il controllo grammaticale "
            "e la Stanza di Dexter. Cambiarla non riscrive né traduce mai "
            "il tuo testo.",
        "Use project language": "Usa la lingua del progetto",
        "Transcription language:": "Lingua di trascrizione:",
    },
}


def ui_language() -> str:
    """The current UI language code (global setting; invalid → English)."""
    try:
        from storyplanner.settings import get_manager
        code = str(get_manager().get("ui_language_code") or "").strip().lower()
    except Exception:
        code = ""
    return code if code in _CATALOG or code == "en" else DEFAULT_UI_LANGUAGE


def tr(text: str) -> str:
    """Translate a user-facing label for the current UI language.

    English (default) returns *text* unchanged; other locales fall back to
    English for any string not in their catalog (partial coverage)."""
    locale = ui_language()
    if locale == "en":
        return text
    return _CATALOG.get(locale, {}).get(text, text)


def coverage(locale: str) -> int:
    """Number of translated strings for *locale* (0 = unsupported)."""
    return len(_CATALOG.get(locale, {}))
