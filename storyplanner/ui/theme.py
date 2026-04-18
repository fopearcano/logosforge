"""Logosforge — centralized theme with Dark, Light (Green), Light (Warm) palettes."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Palette definitions
# ---------------------------------------------------------------------------

_PALETTES: dict[str, dict[str, str]] = {
    "Dark": {
        "BG_DARK":       "#0f1219",
        "BG_PANEL":      "#161b26",
        "BG_INPUT":      "#1a2030",
        "BG_SIDEBAR":    "#0b0e14",
        "BG_HOVER":      "#222938",
        "BG_PRESSED":    "#1e2533",

        "TEXT_PRIMARY":  "#e5e7eb",
        "TEXT_SECONDARY": "#9ca3af",
        "TEXT_MUTED":    "#6b7280",

        "ACCENT":        "#4ade80",
        "ACCENT_DIM":    "#22c55e",
        "ACCENT_TEXT":   "#ffffff",

        "BORDER":        "#232b3a",
        "BORDER_FOCUS":  "#4ade80",

        "SELECTION_BG":  "#1e3a2a",
        "SELECTION_TEXT": "#ffffff",

        "TABLE_ALT_ROW": "#111620",

        "STATUS_OK":     "#4ade80",
        "STATUS_ERR":    "#f87171",

        "DIFF_ORIGINAL_BG":     "#1a1215",
        "DIFF_ORIGINAL_TEXT":   "#d4a0a0",
        "DIFF_ORIGINAL_BORDER": "#3a2020",
        "DIFF_PROPOSED_BG":     "#121a15",
        "DIFF_PROPOSED_TEXT":   "#a0d4a0",
        "DIFF_PROPOSED_BORDER": "#203a20",

        "LINK_COLOR":    "#4ade80",

        "CARD_BG":       "#181e2a",
        "CARD_BORDER":   "#232b3a",
        "CARD_HERO_BG":  "#162216",
        "CARD_HERO_BORDER": "#22543d",
        "CARD_BEAT_BG":  "#161b26",
        "CARD_KEY_BEAT_BG": "#1f1d14",
        "CARD_BEAT_BORDER": "#607d8b",
        "CARD_KEY_BEAT_BORDER": "#ff9800",

        "SIDEBAR_ACTIVE_BG": "#1e3a2a",
        "SIDEBAR_ACTIVE_TEXT": "#4ade80",
        "SIDEBAR_ICON":  "#6b7280",

        "BTN_PRIMARY_BG": "#22c55e",
        "BTN_PRIMARY_TEXT": "#0f1219",
        "BTN_PRIMARY_HOVER": "#16a34a",
        "BTN_PRIMARY_BORDER": "#22c55e",

        "SCROLLBAR_BG":  "#0f1219",
        "SCROLLBAR_HANDLE": "#2a3344",
        "SCROLLBAR_HOVER": "#3b4a60",
    },

    "Light (Green)": {
        "BG_DARK":       "#f4f7f5",
        "BG_PANEL":      "#ffffff",
        "BG_INPUT":      "#f0f4f1",
        "BG_SIDEBAR":    "#eaf0ec",
        "BG_HOVER":      "#e2ece5",
        "BG_PRESSED":    "#d5e3d9",

        "TEXT_PRIMARY":  "#1a2e22",
        "TEXT_SECONDARY": "#4b6455",
        "TEXT_MUTED":    "#7a9484",

        "ACCENT":        "#16a34a",
        "ACCENT_DIM":    "#22c55e",
        "ACCENT_TEXT":   "#ffffff",

        "BORDER":        "#d0ddd4",
        "BORDER_FOCUS":  "#16a34a",

        "SELECTION_BG":  "#d4edda",
        "SELECTION_TEXT": "#1a2e22",

        "TABLE_ALT_ROW": "#f0f5f1",

        "STATUS_OK":     "#16a34a",
        "STATUS_ERR":    "#dc2626",

        "DIFF_ORIGINAL_BG":     "#fef2f2",
        "DIFF_ORIGINAL_TEXT":   "#991b1b",
        "DIFF_ORIGINAL_BORDER": "#fecaca",
        "DIFF_PROPOSED_BG":     "#f0fdf4",
        "DIFF_PROPOSED_TEXT":   "#166534",
        "DIFF_PROPOSED_BORDER": "#bbf7d0",

        "LINK_COLOR":    "#16a34a",

        "CARD_BG":       "#ffffff",
        "CARD_BORDER":   "#d0ddd4",
        "CARD_HERO_BG":  "#ecfdf5",
        "CARD_HERO_BORDER": "#a7f3d0",
        "CARD_BEAT_BG":  "#f8faf9",
        "CARD_KEY_BEAT_BG": "#fffbeb",
        "CARD_BEAT_BORDER": "#90a4ae",
        "CARD_KEY_BEAT_BORDER": "#f59e0b",

        "SIDEBAR_ACTIVE_BG": "#d4edda",
        "SIDEBAR_ACTIVE_TEXT": "#16a34a",
        "SIDEBAR_ICON":  "#7a9484",

        "BTN_PRIMARY_BG": "#16a34a",
        "BTN_PRIMARY_TEXT": "#ffffff",
        "BTN_PRIMARY_HOVER": "#15803d",
        "BTN_PRIMARY_BORDER": "#16a34a",

        "SCROLLBAR_BG":  "#f4f7f5",
        "SCROLLBAR_HANDLE": "#c5d0c8",
        "SCROLLBAR_HOVER": "#a0b0a5",
    },

    "Light (Warm)": {
        "BG_DARK":       "#f7f5f2",
        "BG_PANEL":      "#ffffff",
        "BG_INPUT":      "#f3f0ec",
        "BG_SIDEBAR":    "#efecea",
        "BG_HOVER":      "#e8e4df",
        "BG_PRESSED":    "#ddd8d1",

        "TEXT_PRIMARY":  "#2c2418",
        "TEXT_SECONDARY": "#6b5d4f",
        "TEXT_MUTED":    "#9a8d7f",

        "ACCENT":        "#b8860b",
        "ACCENT_DIM":    "#d4a017",
        "ACCENT_TEXT":   "#ffffff",

        "BORDER":        "#ddd8d1",
        "BORDER_FOCUS":  "#b8860b",

        "SELECTION_BG":  "#f5ecd8",
        "SELECTION_TEXT": "#2c2418",

        "TABLE_ALT_ROW": "#f5f2ef",

        "STATUS_OK":     "#65a30d",
        "STATUS_ERR":    "#dc2626",

        "DIFF_ORIGINAL_BG":     "#fef2f2",
        "DIFF_ORIGINAL_TEXT":   "#991b1b",
        "DIFF_ORIGINAL_BORDER": "#fecaca",
        "DIFF_PROPOSED_BG":     "#fefce8",
        "DIFF_PROPOSED_TEXT":   "#713f12",
        "DIFF_PROPOSED_BORDER": "#fef08a",

        "LINK_COLOR":    "#b8860b",

        "CARD_BG":       "#ffffff",
        "CARD_BORDER":   "#ddd8d1",
        "CARD_HERO_BG":  "#fefce8",
        "CARD_HERO_BORDER": "#fde68a",
        "CARD_BEAT_BG":  "#faf8f5",
        "CARD_KEY_BEAT_BG": "#fffbeb",
        "CARD_BEAT_BORDER": "#b8a590",
        "CARD_KEY_BEAT_BORDER": "#f59e0b",

        "SIDEBAR_ACTIVE_BG": "#f5ecd8",
        "SIDEBAR_ACTIVE_TEXT": "#b8860b",
        "SIDEBAR_ICON":  "#9a8d7f",

        "BTN_PRIMARY_BG": "#b8860b",
        "BTN_PRIMARY_TEXT": "#ffffff",
        "BTN_PRIMARY_HOVER": "#996e09",
        "BTN_PRIMARY_BORDER": "#b8860b",

        "SCROLLBAR_BG":  "#f7f5f2",
        "SCROLLBAR_HANDLE": "#d0cac0",
        "SCROLLBAR_HOVER": "#b0a898",
    },
}

# ---------------------------------------------------------------------------
# Active palette — module-level attributes updated by set_palette()
# ---------------------------------------------------------------------------

_current_palette: str = "Dark"


def _apply(palette: dict[str, str]) -> None:
    g = globals()
    for key, value in palette.items():
        g[key] = value


# Initialize with Dark
_apply(_PALETTES["Dark"])

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

PALETTE_NAMES: list[str] = list(_PALETTES.keys())


def current_palette() -> str:
    return _current_palette


def set_palette(name: str) -> None:
    global _current_palette
    if name not in _PALETTES:
        return
    _current_palette = name
    _apply(_PALETTES[name])


def get(key: str) -> str:
    """Get a color value by key name from the active palette."""
    return globals().get(key, "#ff00ff")


# ---------------------------------------------------------------------------
# build_stylesheet — reads current module-level values at call time
# ---------------------------------------------------------------------------

def build_stylesheet() -> str:
    return f"""
    /* -- Base -- */
    QWidget {{
        background-color: {BG_DARK};
        color: {TEXT_PRIMARY};
        font-size: 13px;
    }}

    QMainWindow {{
        background-color: {BG_DARK};
    }}

    /* -- Labels -- */
    QLabel {{
        background-color: transparent;
        padding: 1px;
    }}

    /* -- Buttons -- */
    QPushButton {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 6px 16px;
        min-height: 22px;
    }}
    QPushButton:hover {{
        background-color: {BG_HOVER};
        border-color: {ACCENT_DIM};
    }}
    QPushButton:pressed {{
        background-color: {BG_PRESSED};
        border-color: {ACCENT};
    }}
    QPushButton:disabled {{
        color: {TEXT_MUTED};
        border-color: {BG_INPUT};
    }}
    QPushButton:flat {{
        border: none;
        background-color: transparent;
        padding: 2px 6px;
    }}
    QPushButton:flat:hover {{
        background-color: {BG_HOVER};
        border-radius: 4px;
    }}

    /* -- Sidebar -- */
    #sidebar {{
        background-color: {BG_SIDEBAR};
        border-right: 1px solid {BORDER};
    }}
    #sidebar QPushButton {{
        border: none;
        border-radius: 6px;
        text-align: left;
        padding: 8px 14px;
        margin: 1px 8px;
        background-color: transparent;
        color: {TEXT_SECONDARY};
        font-size: 12px;
    }}
    #sidebar QPushButton:hover {{
        background-color: {BG_HOVER};
        color: {TEXT_PRIMARY};
    }}
    #sidebar QPushButton:pressed {{
        background-color: {SIDEBAR_ACTIVE_BG};
        color: {SIDEBAR_ACTIVE_TEXT};
    }}
    #sidebar QPushButton:checked {{
        background-color: {SIDEBAR_ACTIVE_BG};
        color: {SIDEBAR_ACTIVE_TEXT};
        font-weight: bold;
    }}

    /* -- Line edits -- */
    QLineEdit {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 6px 10px;
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_TEXT};
    }}
    QLineEdit:focus {{
        border-color: {BORDER_FOCUS};
    }}

    /* -- Plain text edits -- */
    QPlainTextEdit {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 6px;
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_TEXT};
    }}
    QPlainTextEdit:focus {{
        border-color: {BORDER_FOCUS};
    }}

    /* -- Content editor (scene writing area) -- */
    #contentEditor {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border: none;
        border-radius: 8px;
        padding: 28px 32px;
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_TEXT};
    }}

    /* -- Text browser -- */
    QTextBrowser {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 6px;
    }}

    /* -- Combo boxes -- */
    QComboBox {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 5px 10px;
        min-height: 22px;
    }}
    QComboBox:focus {{
        border-color: {BORDER_FOCUS};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {TEXT_SECONDARY};
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 4px;
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_TEXT};
        outline: none;
    }}

    /* -- Checkboxes -- */
    QCheckBox {{
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {BORDER};
        border-radius: 4px;
        background-color: {BG_INPUT};
    }}
    QCheckBox::indicator:checked {{
        background-color: {ACCENT};
        border-color: {ACCENT};
    }}

    /* -- List widgets -- */
    QListWidget {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        outline: none;
        padding: 2px;
    }}
    QListWidget::item {{
        padding: 4px 10px;
        border-radius: 4px;
        margin: 1px 2px;
    }}
    QListWidget::item:selected {{
        background-color: {SELECTION_BG};
        color: {SELECTION_TEXT};
    }}
    QListWidget::item:hover {{
        background-color: {BG_HOVER};
    }}

    /* -- Table widgets -- */
    QTableWidget {{
        background-color: {BG_DARK};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        gridline-color: {BORDER};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 5px;
    }}
    QTableWidget::item:selected {{
        background-color: {SELECTION_BG};
        color: {SELECTION_TEXT};
    }}
    QHeaderView::section {{
        background-color: {BG_PANEL};
        color: {TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {BORDER};
        border-right: 1px solid {BORDER};
        padding: 6px 10px;
        font-weight: bold;
    }}

    /* -- Scroll area -- */
    QScrollArea {{
        border: none;
    }}

    /* -- Scroll bars -- */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 8px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background-color: {SCROLLBAR_HANDLE};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {SCROLLBAR_HOVER};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {SCROLLBAR_HANDLE};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {SCROLLBAR_HOVER};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    /* -- Menu bar -- */
    QMenuBar {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_PRIMARY};
        border-bottom: 1px solid {BORDER};
        padding: 2px;
    }}
    QMenuBar::item {{
        padding: 5px 12px;
        border-radius: 4px;
        background-color: transparent;
    }}
    QMenuBar::item:selected {{
        background-color: {BG_HOVER};
    }}

    /* -- Menus -- */
    QMenu {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 28px 6px 16px;
        border-radius: 4px;
        margin: 1px 4px;
    }}
    QMenu::item:selected {{
        background-color: {SELECTION_BG};
        color: {SELECTION_TEXT};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {BORDER};
        margin: 4px 8px;
    }}

    /* -- Message boxes and dialogs -- */
    QMessageBox {{
        background-color: {BG_PANEL};
    }}
    QDialog {{
        background-color: {BG_DARK};
    }}

    /* -- Graphics view -- */
    QGraphicsView {{
        background-color: {BG_PANEL};
        border: 1px solid {BORDER};
        border-radius: 6px;
    }}

    /* -- Splitter -- */
    QSplitter::handle {{
        background-color: {BORDER};
    }}

    /* -- Tool tips -- */
    QToolTip {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 5px 8px;
    }}

    /* -- Frame cards -- */
    QFrame#dashCard, QFrame#projCard {{
        background-color: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 8px;
    }}
    QFrame#heroCard {{
        background-color: {CARD_HERO_BG};
        border: 1px solid {CARD_HERO_BORDER};
        border-radius: 10px;
    }}

    /* -- Appearance selector -- */
    #appearanceBar {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER};
        border-radius: 6px;
    }}
    #appearanceBar QPushButton {{
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        margin: 2px;
        font-size: 11px;
        min-height: 18px;
        background-color: transparent;
        color: {TEXT_MUTED};
    }}
    #appearanceBar QPushButton:hover {{
        background-color: {BG_HOVER};
        color: {TEXT_PRIMARY};
    }}
    #appearanceBar QPushButton:checked {{
        background-color: {SIDEBAR_ACTIVE_BG};
        color: {SIDEBAR_ACTIVE_TEXT};
        font-weight: bold;
    }}
    """


# ---------------------------------------------------------------------------
# HTML helpers — re-generated each time to respect current palette
# ---------------------------------------------------------------------------

HTML_TABLE_BORDER = ""
HTML_TABLE_ALT = ""
HTML_MUTED_TEXT = ""
HTML_STYLES = ""


def _rebuild_html() -> None:
    global HTML_TABLE_BORDER, HTML_TABLE_ALT, HTML_MUTED_TEXT, HTML_STYLES
    HTML_TABLE_BORDER = BORDER
    HTML_TABLE_ALT = TABLE_ALT_ROW
    HTML_MUTED_TEXT = TEXT_MUTED
    HTML_STYLES = f"""
<style>
    body {{ color: {TEXT_PRIMARY}; }}
    table {{ border-collapse: collapse; }}
    th {{ text-align: left; padding: 5px 10px; }}
    td {{ padding: 5px 10px; }}
    tr {{ border-bottom: 1px solid {BORDER}; }}
    h1, h2, h3 {{ color: {TEXT_PRIMARY}; }}
    a {{ color: {LINK_COLOR}; }}
    .muted {{ color: {TEXT_MUTED}; }}
</style>
"""


_rebuild_html()


# ---------------------------------------------------------------------------
# Style helper functions — called at widget construction time
# ---------------------------------------------------------------------------

def primary_btn() -> str:
    return (
        f"QPushButton {{"
        f"  background-color: {BTN_PRIMARY_BG};"
        f"  color: {BTN_PRIMARY_TEXT};"
        f"  border: 1px solid {BTN_PRIMARY_BORDER};"
        f"  border-radius: 6px; padding: 7px 22px;"
        f"  font-weight: bold;"
        f"}}"
        f"QPushButton:hover {{"
        f"  background-color: {BTN_PRIMARY_HOVER};"
        f"}}"
    )


def card_style(object_name: str = "dashCard") -> str:
    return (
        f"QFrame#{object_name} {{ background: {CARD_BG};"
        f" border: 1px solid {CARD_BORDER}; border-radius: 8px; }}"
    )


def hero_card_style() -> str:
    return (
        f"QFrame#heroCard {{ background: {CARD_HERO_BG};"
        f" border: 1px solid {CARD_HERO_BORDER}; border-radius: 10px; }}"
    )


def eyebrow() -> str:
    return (
        f"color: {TEXT_MUTED}; font-size: 11px;"
        f" letter-spacing: 1px; text-transform: uppercase;"
    )


def small_btn() -> str:
    return (
        f"QPushButton {{ background: transparent; color: {TEXT_SECONDARY};"
        f" border: 1px solid {BORDER}; border-radius: 5px;"
        f" padding: 3px 10px; font-size: 11px; }}"
        f"QPushButton:hover {{ background: {BG_HOVER};"
        f" color: {TEXT_PRIMARY}; }}"
    )
