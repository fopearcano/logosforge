"""Project Chat — central panel for long-form, project-aware conversation.

Reuses the existing chat_completion infrastructure, PSYKE context
gatherers, and Connector action system. Messages persist per project
in the ChatMessage table; older messages are folded into a rolling
summary so prompts stay bounded.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QTextOption
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from storyplanner.assistant import chat_completion
from storyplanner.chat_context import build_chat_context, context_summary
from storyplanner.chat_memory import (
    ActionProposal,
    build_memory_frame,
    build_system_prompt,
    heuristic_summary,
    needs_summary_update,
    parse_action_proposals,
    strip_action_blocks,
)
from storyplanner.connector_executor import execute_action
from storyplanner.connector_registry import get_action
from storyplanner.db import Database
from storyplanner.models.models import CHAT_PERSONALITIES
from storyplanner.providers import ProviderConfig
from storyplanner.settings import get_manager as get_settings
from storyplanner.ui import theme

_PERSONALITY_LABELS: dict[str, str] = {
    "default": "Default",
    "mentor": "Mentor",
    "skeptic": "Skeptic",
    "editor": "Editor",
    "brutal": "Brutally honest",
    "whimsical": "Whimsical",
    "minimalist": "Minimalist",
    "philosopher": "Philosopher",
}


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class _ChatWorker(QThread):
    completed = Signal(str, bool)
    failed = Signal(str)

    def __init__(
        self, messages: list[dict], provider: ProviderConfig,
    ) -> None:
        super().__init__()
        self._messages = messages
        self._provider = provider

    def run(self) -> None:
        try:
            result, from_cache = chat_completion(
                self._messages, provider=self._provider, use_cache=False,
            )
            self.completed.emit(result, from_cache)
        except Exception as e:
            self.failed.emit(str(e))


# ---------------------------------------------------------------------------
# Composer (input box that auto-sends on Enter)
# ---------------------------------------------------------------------------

class _Composer(QTextEdit):
    submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatComposer")
        self.setPlaceholderText("Message your project — Enter to send, Shift+Enter for newline")
        self.setAcceptRichText(False)
        self.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.setFixedHeight(96)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            text = self.toPlainText().strip()
            if text:
                self.submitted.emit(text)
                self.clear()
            return
        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Action card (Apply / Discard for a proposed write action)
# ---------------------------------------------------------------------------

class _ActionCard(QFrame):
    apply_requested = Signal(object)  # ActionProposal
    discarded = Signal(object)

    def __init__(
        self, proposal: ActionProposal, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._proposal = proposal
        self.setObjectName("chatActionCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"#chatActionCard {{"
            f"  background-color: {theme.get('BG_INPUT')};"
            f"  border: 1px solid {theme.get('BORDER')};"
            f"  border-radius: 8px;"
            f"  padding: 10px;"
            f"}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header = QLabel(f"Proposed action: {proposal.label}")
        header.setStyleSheet(
            f"color: {theme.get('TEXT_PRIMARY')}; font-weight: 600;"
        )
        layout.addWidget(header)

        action_def = get_action(proposal.action)
        category = action_def.category if action_def else "?"
        meta = QLabel(f"{proposal.action} ({category})")
        meta.setStyleSheet(f"color: {theme.get('TEXT_MUTED')}; font-size: 11px;")
        layout.addWidget(meta)

        if proposal.args:
            preview = QLabel(self._format_args(proposal.args))
            preview.setWordWrap(True)
            preview.setStyleSheet(
                f"color: {theme.get('TEXT_SECONDARY')}; font-size: 12px;"
                f" background: transparent;"
            )
            layout.addWidget(preview)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 4, 0, 0)
        button_row.setSpacing(8)

        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {theme.get('ACCENT')};"
            f"  color: {theme.get('ACCENT_TEXT')};"
            f"  border: none; padding: 6px 14px; border-radius: 6px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {theme.get('ACCENT_DIM')}; }}"
        )
        apply_btn.clicked.connect(lambda: self.apply_requested.emit(self._proposal))

        discard_btn = QPushButton("Discard")
        discard_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {theme.get('TEXT_MUTED')};"
            f"  border: 1px solid {theme.get('BORDER')};"
            f"  padding: 6px 14px; border-radius: 6px;"
            f"}}"
            f"QPushButton:hover {{ color: {theme.get('TEXT_PRIMARY')}; }}"
        )
        discard_btn.clicked.connect(lambda: self.discarded.emit(self._proposal))

        button_row.addWidget(apply_btn)
        button_row.addWidget(discard_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._apply_btn = apply_btn
        self._discard_btn = discard_btn
        self._status_label: QLabel | None = None

    def _format_args(self, args: dict) -> str:
        try:
            return json.dumps(args, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(args)

    def mark_executed(self, message: str) -> None:
        self._apply_btn.setEnabled(False)
        self._discard_btn.setEnabled(False)
        if self._status_label is None:
            self._status_label = QLabel(message)
            self._status_label.setStyleSheet(
                f"color: {theme.get('ACCENT')}; font-size: 11px;"
            )
            self.layout().addWidget(self._status_label)
        else:
            self._status_label.setText(message)


# ---------------------------------------------------------------------------
# Message bubble
# ---------------------------------------------------------------------------

class _MessageBubble(QFrame):
    def __init__(
        self, role: str, content: str, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("chatBubble")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        role_label_text = {
            "user": "You",
            "assistant": "Assistant",
            "system": "System",
        }.get(role, role.capitalize())
        role_label = QLabel(role_label_text)
        role_label.setStyleSheet(
            f"color: {theme.get('TEXT_MUTED')};"
            f" font-size: 11px; text-transform: uppercase;"
            f" letter-spacing: 0.05em;"
        )
        layout.addWidget(role_label)

        body = QLabel(content)
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        body.setStyleSheet(
            f"color: {theme.get('TEXT_PRIMARY')};"
            f" font-size: 14px; line-height: 1.45;"
        )
        layout.addWidget(body)


# ---------------------------------------------------------------------------
# Chat view
# ---------------------------------------------------------------------------

class ChatView(QWidget):
    """Central project chat panel."""

    data_changed = Signal()

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
        get_active_scene_id: Callable[[], int | None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._get_active_scene_id = get_active_scene_id or (lambda: None)
        self._worker: _ChatWorker | None = None
        self._action_cards: list[_ActionCard] = []
        self._typing_label: QLabel | None = None

        settings = self._db.get_project_settings(project_id)
        personality = settings.get("chat_personality", "default")
        if personality not in CHAT_PERSONALITIES:
            personality = "default"
        self._personality = personality

        self._build_ui()
        self._reload_history()

    # -- UI ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        layout.addLayout(self._build_header())

        self._messages_scroll = QScrollArea()
        self._messages_scroll.setWidgetResizable(True)
        self._messages_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._messages_host = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_host)
        self._messages_layout.setContentsMargins(0, 0, 0, 0)
        self._messages_layout.setSpacing(14)
        self._messages_layout.addStretch(1)
        self._messages_scroll.setWidget(self._messages_host)
        layout.addWidget(self._messages_scroll, 1)

        self._composer = _Composer()
        self._composer.submitted.connect(self._on_user_submit)
        layout.addWidget(self._composer)

        self._status_label = QLabel(self._build_status_text())
        self._status_label.setStyleSheet(
            f"color: {theme.get('TEXT_MUTED')}; font-size: 11px;"
        )
        layout.addWidget(self._status_label)

        self.setStyleSheet(
            f"QWidget {{ background-color: {theme.get('BG_PANEL')}; }}"
        )

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 4)
        header.setSpacing(12)

        title = QLabel("Chat")
        title.setStyleSheet(
            f"color: {theme.get('TEXT_PRIMARY')};"
            f" font-size: 22px; font-weight: 600;"
        )
        header.addWidget(title)

        header.addStretch(1)

        personality_label = QLabel("Personality:")
        personality_label.setStyleSheet(f"color: {theme.get('TEXT_MUTED')};")
        header.addWidget(personality_label)

        self._personality_combo = QComboBox()
        for key in CHAT_PERSONALITIES:
            self._personality_combo.addItem(_PERSONALITY_LABELS.get(key, key), key)
        idx = self._personality_combo.findData(self._personality)
        if idx >= 0:
            self._personality_combo.setCurrentIndex(idx)
        self._personality_combo.currentIndexChanged.connect(
            self._on_personality_changed
        )
        header.addWidget(self._personality_combo)

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(
            f"QPushButton {{ color: {theme.get('TEXT_MUTED')};"
            f" background: transparent; border: 1px solid {theme.get('BORDER')};"
            f" padding: 4px 10px; border-radius: 4px; }}"
            f"QPushButton:hover {{ color: {theme.get('TEXT_PRIMARY')}; }}"
        )
        clear_btn.clicked.connect(self._on_clear_clicked)
        header.addWidget(clear_btn)

        return header

    def _build_status_text(self) -> str:
        ctx = context_summary(
            self._db, self._project_id,
            active_scene_id=self._get_active_scene_id(),
        )
        return f"Project memory active · PSYKE context active · Actions require confirmation · {ctx}"

    # -- History rendering ---------------------------------------------------

    def _reload_history(self) -> None:
        for i in reversed(range(self._messages_layout.count() - 1)):
            item = self._messages_layout.itemAt(i)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._action_cards = []
        for msg in self._db.get_chat_messages(self._project_id):
            self._render_stored_message(msg)
        self._scroll_to_bottom()

    def _render_stored_message(self, msg) -> None:
        bubble = _MessageBubble(msg.role, msg.content)
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, bubble,
        )
        if msg.role != "assistant" or not msg.metadata_json:
            return
        try:
            metadata = json.loads(msg.metadata_json)
        except (json.JSONDecodeError, TypeError):
            return
        proposals_data = metadata.get("proposals", [])
        executed = metadata.get("executed", {})
        for entry in proposals_data:
            proposal = ActionProposal(
                action=entry.get("action", ""),
                args=entry.get("args", {}),
                label=entry.get("label", entry.get("action", "")),
                raw=entry.get("raw", ""),
            )
            card = self._add_action_card(proposal)
            status = executed.get(proposal.action)
            if status:
                card.mark_executed(status)

    def _add_message_bubble(self, role: str, content: str) -> None:
        bubble = _MessageBubble(role, content)
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, bubble,
        )
        self._scroll_to_bottom()

    def _add_action_card(self, proposal: ActionProposal) -> _ActionCard:
        card = _ActionCard(proposal)
        card.apply_requested.connect(self._on_apply_action)
        card.discarded.connect(self._on_discard_action)
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, card,
        )
        self._action_cards.append(card)
        self._scroll_to_bottom()
        return card

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(0, lambda: self._messages_scroll.verticalScrollBar().setValue(
            self._messages_scroll.verticalScrollBar().maximum(),
        ))

    # -- Settings ------------------------------------------------------------

    def _on_personality_changed(self) -> None:
        self._personality = self._personality_combo.currentData()
        settings = self._db.get_project_settings(self._project_id)
        settings["chat_personality"] = self._personality
        self._db.save_project_settings(self._project_id, settings)

    # -- Submit flow ---------------------------------------------------------

    def _on_user_submit(self, text: str) -> None:
        if text.startswith("/"):
            handled = self._handle_slash_command(text)
            if handled:
                return
        self._db.add_chat_message(self._project_id, "user", text)
        self._add_message_bubble("user", text)
        self._send_to_assistant()

    def _send_to_assistant(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        provider = self._build_provider()
        if provider is None:
            self._add_message_bubble(
                "system",
                "No AI provider configured. Open Settings → AI to set one up.",
            )
            return
        scene_id = self._get_active_scene_id()
        context = build_chat_context(
            self._db, self._project_id, active_scene_id=scene_id,
        )
        system_prompt = build_system_prompt(self._personality, context)

        all_messages = self._db.get_chat_messages(self._project_id)
        summary_record = self._db.get_chat_summary(self._project_id)
        summary_text = summary_record.summary if summary_record else ""
        last_summarized_id = summary_record.last_summarized_message_id if summary_record else 0

        frame = build_memory_frame(
            all_messages, summary_text, last_summarized_id,
        )

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if frame.summary:
            messages.append({
                "role": "system",
                "content": f"Earlier conversation summary:\n{frame.summary}",
            })
        messages.extend(frame.recent)

        self._show_typing_indicator()
        self._worker = _ChatWorker(messages, provider)
        self._worker.completed.connect(self._on_completion)
        self._worker.failed.connect(self._on_failure)
        self._worker.start()

    def _build_provider(self) -> ProviderConfig | None:
        settings = get_settings()
        name = str(settings.get("ai_provider") or "")
        base_url = str(settings.get("ai_base_url") or "")
        model = str(settings.get("ai_model") or "")
        api_key = str(settings.get("ai_api_key") or "")
        if not (name or base_url):
            return None
        return ProviderConfig(
            name=name or "LM Studio",
            base_url=base_url or "http://localhost:1234/v1",
            model=model,
            api_key=api_key,
        )

    def _show_typing_indicator(self) -> None:
        if self._typing_label is not None:
            return
        label = QLabel("Assistant is thinking…")
        label.setStyleSheet(
            f"color: {theme.get('TEXT_MUTED')}; font-style: italic;"
        )
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, label,
        )
        self._typing_label = label
        self._scroll_to_bottom()

    def _hide_typing_indicator(self) -> None:
        if self._typing_label is not None:
            self._typing_label.setParent(None)
            self._typing_label.deleteLater()
            self._typing_label = None

    def _on_completion(self, raw_text: str, _from_cache: bool) -> None:
        self._hide_typing_indicator()
        proposals = parse_action_proposals(raw_text)
        visible = strip_action_blocks(raw_text) or "(no response)"

        metadata: dict = {}
        if proposals:
            metadata["proposals"] = [
                {
                    "action": p.action,
                    "args": p.args,
                    "label": p.label,
                    "raw": p.raw,
                }
                for p in proposals
            ]

        self._db.add_chat_message(
            self._project_id, "assistant", visible,
            metadata=metadata or None,
        )
        self._add_message_bubble("assistant", visible)
        for proposal in proposals:
            self._add_action_card(proposal)

        self._maybe_update_summary()
        self._refresh_status()

    def _on_failure(self, error: str) -> None:
        self._hide_typing_indicator()
        msg = f"Assistant call failed: {error}"
        self._db.add_chat_message(self._project_id, "system", msg)
        self._add_message_bubble("system", msg)

    # -- Action confirmation -------------------------------------------------

    def _on_apply_action(self, proposal: ActionProposal) -> None:
        result = execute_action(
            self._db, self._project_id,
            {"action": proposal.action, "args": proposal.args},
            enforce_settings=False,
        )
        for card in self._action_cards:
            if card._proposal is proposal:
                if result.get("ok"):
                    card.mark_executed("Applied")
                else:
                    card.mark_executed(
                        f"Failed: {result.get('error', 'unknown error')}"
                    )
                self._persist_action_status(
                    proposal,
                    "Applied" if result.get("ok") else f"Failed: {result.get('error', '')}",
                )
                break
        if result.get("ok") and self._on_data_changed is not None:
            self._on_data_changed()

    def _on_discard_action(self, proposal: ActionProposal) -> None:
        for card in self._action_cards:
            if card._proposal is proposal:
                card.mark_executed("Discarded")
                self._persist_action_status(proposal, "Discarded")
                break

    def _persist_action_status(
        self, proposal: ActionProposal, status: str,
    ) -> None:
        messages = self._db.get_chat_messages(self._project_id)
        for msg in reversed(messages):
            if msg.role != "assistant":
                continue
            try:
                metadata = json.loads(msg.metadata_json) if msg.metadata_json else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}
            proposals = metadata.get("proposals") or []
            if any(p.get("action") == proposal.action for p in proposals):
                executed = metadata.get("executed") or {}
                executed[proposal.action] = status
                metadata["executed"] = executed
                self._db.update_chat_message_metadata(msg.id, metadata)
                return

    # -- Slash commands ------------------------------------------------------

    def _handle_slash_command(self, text: str) -> bool:
        cmd = text.strip().lower()
        if cmd == "/series" or cmd.startswith("/series "):
            self._handle_series_command(text)
            return True
        if cmd == "/context":
            ctx = build_chat_context(
                self._db, self._project_id,
                active_scene_id=self._get_active_scene_id(),
            )
            self._db.add_chat_message(self._project_id, "system", "/context")
            self._add_message_bubble("user", text)
            preview = ctx if ctx.strip() else "(no project context yet)"
            self._db.add_chat_message(self._project_id, "system", preview)
            self._add_message_bubble("system", preview)
            return True
        if cmd == "/memory":
            summary = self._db.get_chat_summary(self._project_id)
            text_out = summary.summary if summary else "(no summary yet)"
            self._add_message_bubble("user", text)
            self._add_message_bubble("system", text_out)
            self._db.add_chat_message(self._project_id, "system", text_out)
            return True
        if cmd in ("/clear chat", "/clear"):
            self._add_message_bubble("user", text)
            self._add_message_bubble(
                "system",
                "Type '/clear chat confirm' to actually clear all messages.",
            )
            return True
        if cmd == "/clear chat confirm":
            self._db.clear_chat_messages(self._project_id)
            self._reload_history()
            self._add_message_bubble("system", "Chat cleared.")
            return True
        if cmd == "/summarize chat":
            self._add_message_bubble("user", text)
            self._maybe_update_summary(force=True)
            summary = self._db.get_chat_summary(self._project_id)
            out = summary.summary if summary else "(nothing to summarize)"
            self._add_message_bubble("system", out)
            return True
        return False

    def _handle_series_command(self, text: str) -> None:
        """Render a /series … response (only meaningful for Series projects)."""
        sub = text.strip()[len("/series"):].strip()
        self._add_message_bubble("user", text)
        try:
            from storyplanner.narrative_engines import engine_for_project
            project = self._db.get_project_by_id(self._project_id)
            is_series = engine_for_project(project).name == "series"
        except Exception:
            is_series = False
        if not is_series:
            out = "/series commands are only available for Series-engine projects."
        else:
            from storyplanner.series_review import format_series_command
            out = format_series_command(self._db, self._project_id, sub)
        self._db.add_chat_message(self._project_id, "system", out)
        self._add_message_bubble("system", out)

    # -- Memory --------------------------------------------------------------

    def _maybe_update_summary(self, force: bool = False) -> None:
        all_messages = self._db.get_chat_messages(self._project_id)
        summary_record = self._db.get_chat_summary(self._project_id)
        last_id = summary_record.last_summarized_message_id if summary_record else 0
        previous = summary_record.summary if summary_record else ""
        if not force and not needs_summary_update(all_messages, last_id):
            return
        from storyplanner.chat_memory import RECENT_WINDOW
        if force:
            new_messages = [m for m in all_messages if (m.id or 0) > last_id]
        else:
            older = all_messages[:-RECENT_WINDOW] if len(all_messages) > RECENT_WINDOW else []
            new_messages = [m for m in older if (m.id or 0) > last_id]
        if not new_messages:
            return
        new_summary, new_last_id = heuristic_summary(previous, new_messages)
        self._db.update_chat_summary(self._project_id, new_summary, new_last_id)

    # -- Misc ----------------------------------------------------------------

    def _on_clear_clicked(self) -> None:
        self._handle_slash_command("/clear chat")

    def _refresh_status(self) -> None:
        self._status_label.setText(self._build_status_text())
