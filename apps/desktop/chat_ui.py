from __future__ import annotations

import re
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Callable

from echo_core.ai.base import ChatMessage
from echo_core.chat_history import ChatHistoryStore
from echo_core.conversation import ConversationEngine


BG = "#202123"
SIDEBAR_BG = "#171717"
PANEL_BG = "#2b2c2f"
INPUT_BG = "#303136"
TEXT = "#ececf1"
MUTED = "#9b9ca3"
ACCENT = "#10a37f"
BORDER = "#424348"
CODE_BG = "#111214"
CODE_HEADER_BG = "#1b1c1f"
USER_BG = "#343541"
ASSISTANT_BG = "#202123"
DANGER = "#c94b4b"


class EchoChatUI:
    def __init__(
        self,
        engine: ConversationEngine,
        echo_name: str = "ECHO-7",
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.engine = engine
        self.echo_name = echo_name
        self.on_close = on_close

        self.history_store = ChatHistoryStore()

        self.current_chat_id: str | None = None
        self.current_cancel_event: threading.Event | None = None
        self.worker_thread: threading.Thread | None = None

        self.generating = False
        self.current_response = ""
        self.current_user_message = ""

        self.root = tk.Tk()
        self.root.title(self.echo_name)
        self.root.geometry("1180x760")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self._close_window,
        )

        self._build_layout()
        self._refresh_chat_list()

        chats = self.history_store.list_chats()

        if chats:
            self._open_chat(chats[0].id)
        else:
            self._create_new_chat()

    def _build_layout(self) -> None:
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.sidebar = tk.Frame(
            self.root,
            bg=SIDEBAR_BG,
            width=260,
        )
        self.sidebar.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        self.sidebar.grid_propagate(False)

        self.main = tk.Frame(
            self.root,
            bg=BG,
        )
        self.main.grid(
            row=0,
            column=1,
            sticky="nsew",
        )

        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        self._build_sidebar()
        self._build_header()
        self._build_chat_area()
        self._build_input_area()

    def _build_sidebar(self) -> None:
        title = tk.Label(
            self.sidebar,
            text=self.echo_name,
            bg=SIDEBAR_BG,
            fg=TEXT,
            font=("Segoe UI", 17, "bold"),
            anchor="w",
        )
        title.pack(
            fill="x",
            padx=16,
            pady=(18, 14),
        )

        self.new_chat_button = tk.Button(
            self.sidebar,
            text="+  New Chat",
            command=self._create_new_chat,
            bg=PANEL_BG,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 11),
            cursor="hand2",
            anchor="w",
            padx=14,
            pady=10,
        )
        self.new_chat_button.pack(
            fill="x",
            padx=12,
            pady=(0, 18),
        )

        recent_label = tk.Label(
            self.sidebar,
            text="Recent chats",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        recent_label.pack(
            fill="x",
            padx=18,
            pady=(0, 8),
        )

        history_container = tk.Frame(
            self.sidebar,
            bg=SIDEBAR_BG,
        )
        history_container.pack(
            fill="both",
            expand=True,
        )

        self.history_canvas = tk.Canvas(
            history_container,
            bg=SIDEBAR_BG,
            highlightthickness=0,
            bd=0,
        )

        scrollbar = tk.Scrollbar(
            history_container,
            orient="vertical",
            command=self.history_canvas.yview,
        )

        self.history_frame = tk.Frame(
            self.history_canvas,
            bg=SIDEBAR_BG,
        )

        self.history_window = self.history_canvas.create_window(
            (0, 0),
            window=self.history_frame,
            anchor="nw",
        )

        self.history_canvas.configure(
            yscrollcommand=scrollbar.set,
        )

        self.history_canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        self.history_frame.bind(
            "<Configure>",
            lambda event: self.history_canvas.configure(
                scrollregion=self.history_canvas.bbox("all")
            ),
        )

        self.history_canvas.bind(
            "<Configure>",
            self._resize_history_frame,
        )

    def _resize_history_frame(self, event) -> None:
        self.history_canvas.itemconfigure(
            self.history_window,
            width=event.width,
        )

    def _build_header(self) -> None:
        header = tk.Frame(
            self.main,
            bg=BG,
            height=64,
        )
        header.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        header.grid_propagate(False)

        self.chat_title_label = tk.Label(
            header,
            text="New Chat",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 13, "bold"),
        )
        self.chat_title_label.pack(
            side="left",
            padx=24,
            pady=18,
        )

        status = tk.Label(
            header,
            text="●  Brain Online",
            bg=BG,
            fg=ACCENT,
            font=("Segoe UI", 10, "bold"),
        )
        status.pack(
            side="right",
            padx=24,
        )

    def _build_chat_area(self) -> None:
        container = tk.Frame(
            self.main,
            bg=BG,
        )
        container.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.chat_canvas = tk.Canvas(
            container,
            bg=BG,
            highlightthickness=0,
            bd=0,
        )

        scrollbar = tk.Scrollbar(
            container,
            orient="vertical",
            command=self.chat_canvas.yview,
        )

        self.messages_frame = tk.Frame(
            self.chat_canvas,
            bg=BG,
        )

        self.messages_window = self.chat_canvas.create_window(
            (0, 0),
            window=self.messages_frame,
            anchor="nw",
        )

        self.chat_canvas.configure(
            yscrollcommand=scrollbar.set,
        )

        self.chat_canvas.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        self.messages_frame.bind(
            "<Configure>",
            self._update_chat_scroll_region,
        )

        self.chat_canvas.bind(
            "<Configure>",
            self._resize_messages_frame,
        )

        self.chat_canvas.bind_all(
            "<MouseWheel>",
            self._mousewheel,
        )

    def _update_chat_scroll_region(self, event=None) -> None:
        self.chat_canvas.configure(
            scrollregion=self.chat_canvas.bbox("all")
        )

    def _resize_messages_frame(self, event) -> None:
        self.chat_canvas.itemconfigure(
            self.messages_window,
            width=event.width,
        )

    def _mousewheel(self, event) -> None:
        try:
            self.chat_canvas.yview_scroll(
                int(-1 * (event.delta / 120)),
                "units",
            )
        except tk.TclError:
            pass

    def _build_input_area(self) -> None:
        input_outer = tk.Frame(
            self.main,
            bg=BG,
        )
        input_outer.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=70,
            pady=(10, 22),
        )

        input_outer.grid_columnconfigure(
            0,
            weight=1,
        )

        input_box_frame = tk.Frame(
            input_outer,
            bg=INPUT_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        input_box_frame.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        input_box_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self.input_text = tk.Text(
            input_box_frame,
            height=3,
            wrap="word",
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 11),
            padx=14,
            pady=12,
        )
        self.input_text.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        self.input_text.bind(
            "<Return>",
            self._handle_enter,
        )

        self.input_text.bind(
            "<Shift-Return>",
            self._handle_shift_enter,
        )

        self.send_button = tk.Button(
            input_box_frame,
            text="↑",
            command=self._send_or_stop,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 14, "bold"),
            width=3,
            cursor="hand2",
        )
        self.send_button.grid(
            row=0,
            column=1,
            padx=(5, 10),
            pady=10,
            sticky="ns",
        )

        hint = tk.Label(
            input_outer,
            text="Enter to send  •  Shift+Enter for new line",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 8),
        )
        hint.grid(
            row=1,
            column=0,
            pady=(7, 0),
        )

    def _handle_enter(self, event):
        if event.state & 0x0001:
            return None

        self._send_or_stop()
        return "break"

    def _handle_shift_enter(self, event):
        return None

    def _send_or_stop(self) -> None:
        if self.generating:
            self._stop_generation()
            return

        self._send_message()

    def _send_message(self) -> None:
        message = self.input_text.get(
            "1.0",
            "end-1c",
        ).strip()

        if not message:
            return

        if self.current_chat_id is None:
            self._create_new_chat()

        chat_id = self.current_chat_id

        if chat_id is None:
            return

        self.input_text.delete(
            "1.0",
            "end",
        )

        existing_messages = self.history_store.get_messages(
            chat_id
        )

        if not existing_messages:
            title = self.history_store.auto_title_from_message(
                chat_id,
                message,
            )
            self.chat_title_label.configure(
                text=title,
            )
            self._refresh_chat_list()

        self._render_user_message(
            message
        )

        self.current_user_message = message
        self.current_response = ""

        self.generating = True
        self.current_cancel_event = threading.Event()

        self._set_generating_state(
            True
        )

        response_container = self._create_assistant_container()

        response_body = tk.Frame(
            response_container,
            bg=ASSISTANT_BG,
        )
        response_body.pack(
            fill="x",
            padx=4,
            pady=(4, 8),
        )

        streaming_label = tk.Label(
            response_body,
            text="",
            bg=ASSISTANT_BG,
            fg=TEXT,
            font=("Segoe UI", 11),
            justify="left",
            anchor="nw",
            wraplength=720,
        )
        streaming_label.pack(
            fill="x",
            anchor="w",
        )

        def emit_chunk(chunk: str) -> None:
            self.root.after(
                0,
                self._append_stream_chunk,
                streaming_label,
                chunk,
            )

        cancel_event = self.current_cancel_event

        def worker() -> None:
            turn = self.engine.stream_message(
                message,
                emit_chunk=emit_chunk,
                cancel_event=cancel_event,
            )

            self.root.after(
                0,
                self._generation_finished,
                chat_id,
                message,
                turn,
                response_container,
                streaming_label,
            )

        self.worker_thread = threading.Thread(
            target=worker,
            daemon=True,
        )
        self.worker_thread.start()

    def _append_stream_chunk(
        self,
        label: tk.Label,
        chunk: str,
    ) -> None:
        if not label.winfo_exists():
            return

        self.current_response += chunk

        label.configure(
            text=self.current_response,
        )

        self._scroll_to_bottom()

    def _generation_finished(
        self,
        chat_id: str,
        user_message: str,
        turn,
        response_container: tk.Frame,
        streaming_label: tk.Label,
    ) -> None:
        cancelled = (
            turn.error_message == "generation cancelled"
        )

        response_text = turn.reply.strip()

        self.generating = False
        self.current_cancel_event = None
        self.worker_thread = None

        self._set_generating_state(
            False
        )

        if self.current_chat_id != chat_id:
            return

        if cancelled:
            if response_text:
                streaming_label.configure(
                    text=response_text
                )

                stopped = tk.Label(
                    response_container,
                    text="Stopped",
                    bg=ASSISTANT_BG,
                    fg=MUTED,
                    font=("Segoe UI", 8),
                )
                stopped.pack(
                    anchor="w",
                    pady=(0, 3),
                )

                self._render_response_actions(
                    response_container,
                    response_text,
                )
            else:
                response_container.destroy()

            self.current_response = ""
            self.current_user_message = ""

            self.input_text.focus_set()
            return

        if not turn.succeeded:
            error_text = response_text or "Something went wrong."

            streaming_label.configure(
                text=error_text
            )

            self._render_response_actions(
                response_container,
                error_text,
            )

            self.current_response = ""
            self.current_user_message = ""

            self.input_text.focus_set()
            return

        self.history_store.add_message(
            chat_id,
            "user",
            user_message,
        )

        self.history_store.add_message(
            chat_id,
            "assistant",
            response_text,
        )

        streaming_label.destroy()

        self._render_markdown_content(
            response_container,
            response_text,
        )

        self._render_response_actions(
            response_container,
            response_text,
        )

        self.current_response = ""
        self.current_user_message = ""

        self._refresh_chat_list()
        self._scroll_to_bottom()

        self.input_text.focus_set()

    def _stop_generation(self) -> None:
        if not self.generating:
            return

        if self.current_cancel_event is not None:
            self.current_cancel_event.set()

        self.send_button.configure(
            text="…",
            state="disabled",
        )

    def _set_generating_state(
        self,
        generating: bool,
    ) -> None:
        if generating:
            self.send_button.configure(
                text="■",
                bg=DANGER,
                state="normal",
            )

            self.input_text.configure(
                state="disabled",
            )

        else:
            self.send_button.configure(
                text="↑",
                bg=ACCENT,
                state="normal",
            )

            self.input_text.configure(
                state="normal",
            )

    def _create_new_chat(self) -> None:
        if self.generating:
            self._stop_generation()
            self.root.after(
                100,
                self._wait_then_create_new_chat,
            )
            return

        self._perform_create_new_chat()

    def _wait_then_create_new_chat(self) -> None:
        if self.generating:
            self.root.after(
                100,
                self._wait_then_create_new_chat,
            )
            return

        self._perform_create_new_chat()

    def _perform_create_new_chat(self) -> None:
        self.engine.clear_history()

        self.current_chat_id = self.history_store.create_chat(
            "New Chat"
        )

        self.chat_title_label.configure(
            text="New Chat"
        )

        self._clear_messages()
        self._render_welcome()
        self._refresh_chat_list()

        self.input_text.configure(
            state="normal"
        )
        self.input_text.focus_set()

    def _open_chat(self, chat_id: str) -> None:
        if (
            chat_id == self.current_chat_id
            and not self.generating
        ):
            return

        if self.generating:
            self._stop_generation()
            self.root.after(
                100,
                lambda: self._wait_then_open_chat(
                    chat_id
                ),
            )
            return

        self._perform_open_chat(
            chat_id
        )

    def _wait_then_open_chat(
        self,
        chat_id: str,
    ) -> None:
        if self.generating:
            self.root.after(
                100,
                lambda: self._wait_then_open_chat(
                    chat_id
                ),
            )
            return

        self._perform_open_chat(
            chat_id
        )

    def _perform_open_chat(
        self,
        chat_id: str,
    ) -> None:
        if not self.history_store.chat_exists(
            chat_id
        ):
            return

        chats = self.history_store.list_chats()

        selected_chat = next(
            (
                chat
                for chat in chats
                if chat.id == chat_id
            ),
            None,
        )

        if selected_chat is None:
            return

        messages = self.history_store.get_messages(
            chat_id
        )

        engine_messages = [
            ChatMessage(
                role=message.role,
                content=message.content,
            )
            for message in messages
        ]

        self.engine.load_history(
            engine_messages
        )

        self.current_chat_id = chat_id

        self.chat_title_label.configure(
            text=selected_chat.title
        )

        self._clear_messages()

        if not messages:
            self._render_welcome()
        else:
            for message in messages:
                if message.role == "user":
                    self._render_user_message(
                        message.content
                    )
                elif message.role == "assistant":
                    self._render_assistant_message(
                        message.content
                    )

        self._refresh_chat_list()
        self._scroll_to_bottom()

        self.input_text.focus_set()

    def _delete_chat(
        self,
        chat_id: str,
    ) -> None:
        if self.generating:
            return

        confirmed = messagebox.askyesno(
            "Delete chat",
            "Delete this conversation?",
            parent=self.root,
        )

        if not confirmed:
            return

        deleting_current = (
            chat_id == self.current_chat_id
        )

        self.history_store.delete_chat(
            chat_id
        )

        if deleting_current:
            self.current_chat_id = None
            self.engine.clear_history()

            chats = self.history_store.list_chats()

            if chats:
                self._open_chat(
                    chats[0].id
                )
            else:
                self._perform_create_new_chat()
        else:
            self._refresh_chat_list()

    def _refresh_chat_list(self) -> None:
        for child in self.history_frame.winfo_children():
            child.destroy()

        chats = self.history_store.list_chats()

        for chat in chats:
            selected = (
                chat.id == self.current_chat_id
            )

            row_bg = (
                PANEL_BG
                if selected
                else SIDEBAR_BG
            )

            row = tk.Frame(
                self.history_frame,
                bg=row_bg,
            )
            row.pack(
                fill="x",
                padx=8,
                pady=2,
            )

            title_button = tk.Button(
                row,
                text=chat.title,
                command=lambda cid=chat.id: self._open_chat(
                    cid
                ),
                bg=row_bg,
                fg=TEXT,
                activebackground=PANEL_BG,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                anchor="w",
                font=("Segoe UI", 9),
                cursor="hand2",
                padx=8,
                pady=8,
            )
            title_button.pack(
                side="left",
                fill="x",
                expand=True,
            )

            delete_button = tk.Button(
                row,
                text="×",
                command=lambda cid=chat.id: self._delete_chat(
                    cid
                ),
                bg=row_bg,
                fg=MUTED,
                activebackground=DANGER,
                activeforeground="white",
                relief="flat",
                bd=0,
                width=3,
                cursor="hand2",
                font=("Segoe UI", 10),
            )
            delete_button.pack(
                side="right",
                padx=(0, 3),
            )

    def _clear_messages(self) -> None:
        for child in self.messages_frame.winfo_children():
            child.destroy()

    def _render_welcome(self) -> None:
        wrapper = tk.Frame(
            self.messages_frame,
            bg=BG,
        )
        wrapper.pack(
            fill="both",
            expand=True,
            pady=100,
        )

        title = tk.Label(
            wrapper,
            text=self.echo_name,
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 28, "bold"),
        )
        title.pack()

        subtitle = tk.Label(
            wrapper,
            text="What can I help you with?",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 12),
        )
        subtitle.pack(
            pady=(8, 0)
        )

    def _render_user_message(
        self,
        message: str,
    ) -> None:
        outer = tk.Frame(
            self.messages_frame,
            bg=BG,
        )
        outer.pack(
            fill="x",
            padx=70,
            pady=(16, 4),
        )

        bubble = tk.Frame(
            outer,
            bg=USER_BG,
        )
        bubble.pack(
            side="right",
            anchor="e",
        )

        label = tk.Label(
            bubble,
            text=message,
            bg=USER_BG,
            fg=TEXT,
            justify="left",
            anchor="w",
            wraplength=600,
            font=("Segoe UI", 11),
            padx=14,
            pady=10,
        )
        label.pack()

        self._scroll_to_bottom()

    def _create_assistant_container(
        self,
    ) -> tk.Frame:
        outer = tk.Frame(
            self.messages_frame,
            bg=ASSISTANT_BG,
        )
        outer.pack(
            fill="x",
            padx=70,
            pady=(8, 16),
        )

        name = tk.Label(
            outer,
            text=self.echo_name,
            bg=ASSISTANT_BG,
            fg=TEXT,
            font=("Segoe UI", 9, "bold"),
        )
        name.pack(
            anchor="w",
            pady=(0, 5),
        )

        return outer

    def _render_assistant_message(
        self,
        message: str,
    ) -> None:
        container = self._create_assistant_container()

        self._render_markdown_content(
            container,
            message,
        )

        self._render_response_actions(
            container,
            message,
        )

    def _render_markdown_content(
        self,
        parent: tk.Widget,
        content: str,
    ) -> None:
        pattern = re.compile(
            r"```([a-zA-Z0-9_+\-#.]*)(?:\r?\n)?(.*?)```",
            re.DOTALL,
        )

        position = 0

        for match in pattern.finditer(
            content
        ):
            before = content[
                position:match.start()
            ]

            if before.strip():
                self._render_normal_text(
                    parent,
                    before.strip(),
                )

            language = (
                match.group(1).strip()
                or "code"
            )

            code = match.group(2)

            if code.startswith("\n"):
                code = code[1:]

            code = code.rstrip()

            self._render_code_block(
                parent,
                language,
                code,
            )

            position = match.end()

        remaining = content[position:]

        if remaining.strip():
            self._render_normal_text(
                parent,
                remaining.strip(),
            )

        if not content.strip():
            self._render_normal_text(
                parent,
                ""
            )

    def _render_normal_text(
        self,
        parent: tk.Widget,
        text: str,
    ) -> None:
        label = tk.Label(
            parent,
            text=text,
            bg=ASSISTANT_BG,
            fg=TEXT,
            justify="left",
            anchor="nw",
            wraplength=720,
            font=("Segoe UI", 11),
        )
        label.pack(
            fill="x",
            anchor="w",
            pady=(2, 8),
        )

    def _render_code_block(
        self,
        parent: tk.Widget,
        language: str,
        code: str,
    ) -> None:
        block = tk.Frame(
            parent,
            bg=CODE_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        block.pack(
            fill="x",
            pady=(7, 12),
        )

        header = tk.Frame(
            block,
            bg=CODE_HEADER_BG,
        )
        header.pack(
            fill="x",
        )

        language_label = tk.Label(
            header,
            text=language,
            bg=CODE_HEADER_BG,
            fg=MUTED,
            font=("Consolas", 9),
        )
        language_label.pack(
            side="left",
            padx=10,
            pady=7,
        )

        copy_button = tk.Button(
            header,
            text="Copy",
            bg=CODE_HEADER_BG,
            fg=TEXT,
            activebackground=PANEL_BG,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 9),
        )
        copy_button.pack(
            side="right",
            padx=8,
            pady=4,
        )

        code_text = tk.Text(
            block,
            wrap="none",
            bg=CODE_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            font=("Consolas", 10),
            padx=12,
            pady=10,
            height=self._code_height(code),
        )

        code_text.insert(
            "1.0",
            code,
        )

        code_text.configure(
            state="disabled",
        )

        code_text.pack(
            fill="x",
        )

        copy_button.configure(
            command=lambda value=code, button=copy_button:
            self._copy_code(
                value,
                button,
            )
        )

    def _render_response_actions(
        self,
        parent: tk.Widget,
        response_text: str,
    ) -> None:
        if not response_text.strip():
            return

        actions = tk.Frame(
            parent,
            bg=ASSISTANT_BG,
        )
        actions.pack(
            fill="x",
            pady=(0, 5),
        )

        copy_button = tk.Button(
            actions,
            text="▣  Copy",
            bg=ASSISTANT_BG,
            fg=MUTED,
            activebackground=PANEL_BG,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 9),
            padx=5,
            pady=3,
        )
        copy_button.pack(
            side="left",
        )

        copy_button.configure(
            command=lambda value=response_text, button=copy_button:
            self._copy_response(
                value,
                button,
            )
        )

    @staticmethod
    def _code_height(
        code: str,
    ) -> int:
        lines = max(
            1,
            code.count("\n") + 1,
        )

        return min(
            max(lines, 3),
            18,
        )

    def _copy_response(
        self,
        response_text: str,
        button: tk.Button,
    ) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(
            response_text
        )
        self.root.update_idletasks()

        button.configure(
            text="✓  Copied",
            fg=ACCENT,
        )

        def reset_button() -> None:
            try:
                if button.winfo_exists():
                    button.configure(
                        text="▣  Copy",
                        fg=MUTED,
                    )
            except tk.TclError:
                pass

        self.root.after(
            1500,
            reset_button,
        )

    def _copy_code(
        self,
        code: str,
        button: tk.Button,
    ) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(
            code
        )
        self.root.update_idletasks()

        button.configure(
            text="✓ Copied",
            fg=ACCENT,
        )

        def reset_button() -> None:
            try:
                if button.winfo_exists():
                    button.configure(
                        text="Copy",
                        fg=TEXT,
                    )
            except tk.TclError:
                pass

        self.root.after(
            1300,
            reset_button,
        )

    def _scroll_to_bottom(self) -> None:
        self.root.after_idle(
            self._perform_scroll_to_bottom
        )

    def _perform_scroll_to_bottom(self) -> None:
        try:
            self.chat_canvas.update_idletasks()
            self.chat_canvas.yview_moveto(
                1.0
            )
        except tk.TclError:
            pass

    def _close_window(self) -> None:
        if self.generating:
            if self.current_cancel_event is not None:
                self.current_cancel_event.set()

        if self.on_close is not None:
            try:
                self.on_close()
            except Exception:
                pass

        self.root.destroy()

    def run(self) -> None:
        self.input_text.focus_set()
        self.root.mainloop()


def launch_chat_ui(
    engine: ConversationEngine,
    echo_name: str = "ECHO-7",
    on_close: Callable[[], None] | None = None,
) -> None:
    app = EchoChatUI(
        engine=engine,
        echo_name=echo_name,
        on_close=on_close,
    )

    app.run()