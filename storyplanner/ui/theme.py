"""Dark theme stylesheet for StoryPlanner."""

BG_DARK = "#0f1115"
BG_PANEL = "#161a1f"
BG_INPUT = "#1c2128"
BG_SIDEBAR = "#0b0d10"
BG_HOVER = "#252b33"
BG_PRESSED = "#1a3a2a"

TEXT_PRIMARY = "#e6e6e6"
TEXT_SECONDARY = "#9aa0a6"
TEXT_MUTED = "#6b7280"

ACCENT = "#00ff9c"
ACCENT_DIM = "#00cc7d"
ACCENT_CYAN = "#00c8ff"

BORDER = "#2a2f36"
BORDER_FOCUS = "#00ff9c"

SELECTION_BG = "#1a3a2a"
SELECTION_TEXT = "#00ff9c"

TABLE_ALT_ROW = "#13161b"


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

    /* -- Line edits -- */
    QLineEdit {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 4px 6px;
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_TEXT};
    }}
    QLineEdit:focus {{
        border-color: {ACCENT};
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
        border-color: {ACCENT};
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
        border-color: {ACCENT};
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

    /* -- List widgets -- */
    QListWidget {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 3px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 3px 6px;
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

    /* -- Scroll bars -- */
    QScrollBar:vertical {{
        background-color: {BG_DARK};
        width: 10px;
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
        height: 10px;
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
HTML_TABLE_BORDER = "#2a2f36"
HTML_TABLE_ALT = "#1a1e24"
HTML_MUTED_TEXT = "#6b7280"

HTML_STYLES = f"""
<style>
    body {{ color: {TEXT_PRIMARY}; }}
    table {{ border-collapse: collapse; }}
    th {{ text-align: left; padding: 4px 8px; }}
    td {{ padding: 4px 8px; }}
    tr {{ border-bottom: 1px solid {HTML_TABLE_BORDER}; }}
    h1, h2, h3 {{ color: {TEXT_PRIMARY}; }}
    a {{ color: {ACCENT_CYAN}; }}
    .muted {{ color: {HTML_MUTED_TEXT}; }}
</style>
"""
