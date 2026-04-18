"""Logosforge — centralized dark theme."""

# -- Palette -----------------------------------------------------------------

BG_DARK = "#0b0f1a"
BG_PANEL = "#111827"
BG_INPUT = "#151c2b"
BG_SIDEBAR = "#080c16"
BG_HOVER = "#1e2536"
BG_PRESSED = "#1a2332"

TEXT_PRIMARY = "#e5e7eb"
TEXT_SECONDARY = "#9ca3af"
TEXT_MUTED = "#6b7280"

ACCENT = "#ffffff"
ACCENT_DIM = "#d1d5db"

BORDER = "#1e2536"
BORDER_FOCUS = "#ffffff"

SELECTION_BG = "#1e293b"
SELECTION_TEXT = "#ffffff"

TABLE_ALT_ROW = "#0e1320"

# Functional colors (not branding — keep distinct)
STATUS_OK = "#3fb950"
STATUS_ERR = "#f85149"

DIFF_ORIGINAL_BG = "#1a1215"
DIFF_ORIGINAL_TEXT = "#d4a0a0"
DIFF_ORIGINAL_BORDER = "#3a2020"
DIFF_PROPOSED_BG = "#121a15"
DIFF_PROPOSED_TEXT = "#a0d4a0"
DIFF_PROPOSED_BORDER = "#203a20"

LINK_COLOR = "#94a3b8"

CARD_BG = "#151c2b"
CARD_BEAT_BG = "#131a27"
CARD_KEY_BEAT_BG = "#1a1710"
CARD_BEAT_BORDER = "#607d8b"
CARD_KEY_BEAT_BORDER = "#ff9800"


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
        border-radius: 3px;
        padding: 5px 14px;
        min-height: 20px;
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
        padding: 2px 4px;
    }}
    QPushButton:flat:hover {{
        background-color: {BG_HOVER};
    }}

    /* -- Sidebar -- */
    #sidebar {{
        background-color: {BG_SIDEBAR};
    }}
    #sidebar QPushButton {{
        border: none;
        border-radius: 0;
        text-align: left;
        padding: 7px 16px;
        background-color: transparent;
        color: {TEXT_SECONDARY};
    }}
    #sidebar QPushButton:hover {{
        background-color: {BG_HOVER};
        color: {TEXT_PRIMARY};
    }}
    #sidebar QPushButton:pressed {{
        background-color: {SELECTION_BG};
        color: {ACCENT};
    }}

    /* -- Line edits -- */
    QLineEdit {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 4px 8px;
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
        border-radius: 3px;
        padding: 4px;
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
        border-radius: 4px;
        padding: 24px 28px;
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_TEXT};
    }}

    /* -- Text browser -- */
    QTextBrowser {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 4px;
    }}

    /* -- Combo boxes -- */
    QComboBox {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 4px 8px;
        min-height: 20px;
    }}
    QComboBox:focus {{
        border-color: {BORDER_FOCUS};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
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
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_TEXT};
        outline: none;
    }}

    /* -- Checkboxes -- */
    QCheckBox {{
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {BORDER};
        border-radius: 2px;
        background-color: {BG_INPUT};
    }}
    QCheckBox::indicator:checked {{
        background-color: {SELECTION_BG};
        border-color: {ACCENT};
    }}

    /* -- List widgets -- */
    QListWidget {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 3px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 3px 8px;
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
        gridline-color: {BORDER};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 4px;
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
        padding: 5px 8px;
        font-weight: bold;
    }}

    /* -- Scroll area -- */
    QScrollArea {{
        border: none;
    }}

    /* -- Scroll bars -- */
    QScrollBar:vertical {{
        background-color: {BG_DARK};
        width: 8px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background-color: {BORDER};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {TEXT_MUTED};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: {BG_DARK};
        height: 8px;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {BORDER};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {TEXT_MUTED};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* -- Menu bar -- */
    QMenuBar {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_PRIMARY};
        border-bottom: 1px solid {BORDER};
        padding: 2px;
    }}
    QMenuBar::item {{
        padding: 4px 10px;
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
    }}
    QMenu::item {{
        padding: 5px 24px;
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
        padding: 4px;
    }}
    """


# HTML table styles matching the dark theme
HTML_TABLE_BORDER = BORDER
HTML_TABLE_ALT = TABLE_ALT_ROW
HTML_MUTED_TEXT = TEXT_MUTED

HTML_STYLES = f"""
<style>
    body {{ color: {TEXT_PRIMARY}; }}
    table {{ border-collapse: collapse; }}
    th {{ text-align: left; padding: 4px 8px; }}
    td {{ padding: 4px 8px; }}
    tr {{ border-bottom: 1px solid {HTML_TABLE_BORDER}; }}
    h1, h2, h3 {{ color: {TEXT_PRIMARY}; }}
    a {{ color: {LINK_COLOR}; }}
    .muted {{ color: {HTML_MUTED_TEXT}; }}
</style>
"""
