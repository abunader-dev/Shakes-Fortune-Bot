"""
Shakes & Fortune — RPG Game Main Menu Launcher (Tkinter, zero extra dependencies).

Features:
  - Shakes & Fidget medieval-tavern dark navy & gold UI
  - Multi-character roster: create, switch, 1-click calibrate, or delete characters/servers
  - Built-in Telegram Bot configuration modal with live @BotFather token verification
  - Automatic reuse of already-open Chrome (CDP port 9222) or 1-click Chrome launch
  - Play / Stop bot controls with optional auto-start + live activity console & stats
"""
import asyncio
import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Optional

import profile_manager as pm

# Enable crisp HiDPI rendering on Windows
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# ---- S&F Tavern Color Palette ----
BG_ABYSS = "#07131c"
BG_PANEL = "#0c1e2c"
BG_PANEL_INNER = "#091722"
BG_CARD = "#112a3d"
BG_CARD_HOVER = "#16364e"
BG_CARD_ACTIVE = "#1b4462"
BG_INPUT = "#08151f"

GOLD = "#f5c542"
GOLD_BRIGHT = "#ffe07d"
GOLD_BORDER = "#8f6d24"
BORDER_SUBTLE = "#1f425c"

TEXT_LIGHT = "#edf5fa"
TEXT_MUTED = "#7fa1b8"
TEXT_DIM = "#4f728a"

GREEN = "#1f9d55"
GREEN_HOVER = "#27b865"
RED = "#b83227"
RED_HOVER = "#d93d30"
BLUE_BTN = "#1c4b6e"
BLUE_BTN_HOVER = "#25608c"
AMBER = "#e69f24"
CYAN = "#38bdf8"

FONT_TITLE = ("Georgia", 20, "bold")
FONT_SECTION = ("Segoe UI", 10, "bold")
FONT_CARD_TITLE = ("Segoe UI", 11, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BTN_BIG = ("Segoe UI", 12, "bold")
FONT_BTN = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 9)


class RPGButton(tk.Label):
    """Flat, hover-responsive RPG-styled button (looks crisp on Windows dark themes)."""

    def __init__(
        self,
        parent,
        text: str,
        command,
        *,
        bg: str = BLUE_BTN,
        hover_bg: str = BLUE_BTN_HOVER,
        fg: str = TEXT_LIGHT,
        border: str = GOLD_BORDER,
        font=FONT_BTN,
        padx: int = 16,
        pady: int = 9,
        **kwargs,
    ):
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            padx=padx,
            pady=pady,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=GOLD,
            **kwargs,
        )
        self._bg = bg
        self._hover_bg = hover_bg
        self._fg = fg
        self._border = border
        self._command = command
        self._disabled = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event):
        if not self._disabled:
            self.configure(bg=self._hover_bg, highlightbackground=GOLD)

    def _on_leave(self, _event):
        if not self._disabled:
            self.configure(bg=self._bg, highlightbackground=self._border)

    def _on_click(self, _event):
        if not self._disabled and self._command:
            self._command()

    def set_style(self, *, text: Optional[str] = None, bg: Optional[str] = None, hover_bg: Optional[str] = None, border: Optional[str] = None):
        if text is not None:
            self.configure(text=text)
        if bg is not None:
            self._bg = bg
            self.configure(bg=bg)
        if hover_bg is not None:
            self._hover_bg = hover_bg
        if border is not None:
            self._border = border
            self.configure(highlightbackground=border)

    def set_disabled(self, disabled: bool):
        self._disabled = disabled
        self.configure(
            cursor="arrow" if disabled else "hand2",
            fg=TEXT_DIM if disabled else self._fg,
            bg="#0e202e" if disabled else self._bg,
            highlightbackground=BORDER_SUBTLE if disabled else self._border,
        )


class ShakesFortuneApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Shakes & Fortune — Launcher")
        self.geometry("960x660")
        self.minsize(880, 600)
        self.configure(bg=BG_ABYSS)

        self.config_data = pm.load_config()
        self.bot_proc: Optional[subprocess.Popen] = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.calibrating = False
        self.telegram_username: Optional[str] = None
        self.autostart_var = tk.BooleanVar(value=True)
        self.card_widgets: list[tk.Frame] = []

        self._build_ui()
        self._refresh_roster()
        self._refresh_summary()
        self._check_telegram_async()
        self._poll_status()
        self._drain_logs()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # ---- Top Header Banner ----
        header = tk.Frame(
            self,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground=GOLD_BORDER,
            padx=20,
            pady=14,
        )
        header.pack(fill="x", padx=16, pady=(14, 10))

        title_col = tk.Frame(header, bg=BG_PANEL)
        title_col.pack(side="left")

        tk.Label(
            title_col,
            text="⚔  SHAKES & FORTUNE",
            font=FONT_TITLE,
            fg=GOLD,
            bg=BG_PANEL,
        ).pack(anchor="w")
        tk.Label(
            title_col,
            text="Dr. Abawuwu Auto-Ad Launcher  ·  Resolución Adaptativa 16:9",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL,
        ).pack(anchor="w")

        # Status pills on the right
        pills = tk.Frame(header, bg=BG_PANEL)
        pills.pack(side="right")

        self.pill_chrome = tk.Label(
            pills,
            text="● Chrome: Verificando...",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL_INNER,
            padx=12,
            pady=5,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
        )
        self.pill_chrome.pack(side="left", padx=(0, 8))

        self.pill_bot = tk.Label(
            pills,
            text="● Bot: Detenido",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL_INNER,
            padx=12,
            pady=5,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
        )
        self.pill_bot.pack(side="left")

        # ---- Main Two-Column Body ----
        body = tk.Frame(self, bg=BG_ABYSS)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=6)
        body.rowconfigure(0, weight=1)

        # LEFT COLUMN: Character Roster
        left_panel = tk.Frame(
            body,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground=GOLD_BORDER,
            padx=14,
            pady=14,
        )
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        roster_hdr = tk.Frame(left_panel, bg=BG_PANEL)
        roster_hdr.pack(fill="x", pady=(0, 10))
        tk.Label(
            roster_hdr,
            text="SELECCIÓN DE PERSONAJE",
            font=FONT_SECTION,
            fg=GOLD,
            bg=BG_PANEL,
        ).pack(side="left")

        self.lbl_roster_count = tk.Label(
            roster_hdr,
            text="0 guardados",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL,
        )
        self.lbl_roster_count.pack(side="right")

        # Scrollable roster list
        roster_wrap = tk.Frame(
            left_panel,
            bg=BG_PANEL_INNER,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
        )
        roster_wrap.pack(fill="both", expand=True)

        self.roster_canvas = tk.Canvas(
            roster_wrap,
            bg=BG_PANEL_INNER,
            highlightthickness=0,
        )
        roster_scroll = tk.Scrollbar(
            roster_wrap,
            orient="vertical",
            command=self.roster_canvas.yview,
        )
        self.roster_inner = tk.Frame(self.roster_canvas, bg=BG_PANEL_INNER)
        self.roster_inner.bind(
            "<Configure>",
            lambda _e: self.roster_canvas.configure(scrollregion=self.roster_canvas.bbox("all")),
        )
        self.roster_window = self.roster_canvas.create_window(
            (0, 0), window=self.roster_inner, anchor="nw"
        )
        self.roster_canvas.bind(
            "<Configure>",
            lambda e: self.roster_canvas.itemconfigure(self.roster_window, width=e.width),
        )
        self.roster_canvas.configure(yscrollcommand=roster_scroll.set)
        self.roster_canvas.pack(side="left", fill="both", expand=True)
        roster_scroll.pack(side="right", fill="y")

        # Roster action bar
        roster_btns = tk.Frame(left_panel, bg=BG_PANEL)
        roster_btns.pack(fill="x", pady=(10, 0))

        self.btn_add_char = RPGButton(
            roster_btns,
            text="+ Nuevo",
            command=self._open_new_character_dialog,
            bg=BLUE_BTN,
            hover_bg=BLUE_BTN_HOVER,
            padx=12,
            pady=7,
        )
        self.btn_add_char.pack(side="left", padx=(0, 6))

        self.btn_recal = RPGButton(
            roster_btns,
            text="🎯 Calibrar (1 clic)",
            command=self._recalibrate_selected,
            bg="#1a3d52",
            hover_bg="#235370",
            padx=12,
            pady=7,
        )
        self.btn_recal.pack(side="left", padx=(0, 6))

        self.btn_del_char = RPGButton(
            roster_btns,
            text="Eliminar",
            command=self._delete_selected,
            bg="#3b1b1d",
            hover_bg=RED,
            border="#733438",
            padx=10,
            pady=7,
        )
        self.btn_del_char.pack(side="right")

        # RIGHT COLUMN: Control Panel + Live Log
        right_panel = tk.Frame(body, bg=BG_ABYSS)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right_panel.rowconfigure(1, weight=1)
        right_panel.columnconfigure(0, weight=1)

        # Control card
        ctrl = tk.Frame(
            right_panel,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground=GOLD_BORDER,
            padx=16,
            pady=14,
        )
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        tk.Label(
            ctrl,
            text="PANEL DE CONTROL",
            font=FONT_SECTION,
            fg=GOLD,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(0, 10))

        # Active character + stats grid
        stats = tk.Frame(ctrl, bg=BG_PANEL_INNER, padx=12, pady=10, highlightthickness=1, highlightbackground=BORDER_SUBTLE)
        stats.pack(fill="x", pady=(0, 12))
        stats.columnconfigure(0, weight=1)
        stats.columnconfigure(1, weight=1)
        stats.columnconfigure(2, weight=1)

        self.lbl_stat_char = self._make_stat_tile(stats, 0, "PERSONAJE ACTIVO", "—")
        self.lbl_stat_ads = self._make_stat_tile(stats, 1, "ANUNCIOS VISTOS", "0")
        self.lbl_stat_tg = self._make_stat_tile(stats, 2, "BOT TELEGRAM", "Sin configurar")

        # Big Start / Stop CTA button
        self.btn_play = RPGButton(
            ctrl,
            text="▶  INICIAR BOT",
            command=self._toggle_bot,
            bg=GREEN,
            hover_bg=GREEN_HOVER,
            border="#52d68a",
            font=FONT_BTN_BIG,
            pady=13,
        )
        self.btn_play.pack(fill="x", pady=(0, 8))

        # Autostart checkbox
        chk = tk.Checkbutton(
            ctrl,
            text="Empezar a farmear al instante (también controlable con /start y /stop en Telegram)",
            variable=self.autostart_var,
            bg=BG_PANEL,
            fg=TEXT_MUTED,
            selectcolor=BG_INPUT,
            activebackground=BG_PANEL,
            activeforeground=TEXT_LIGHT,
            font=FONT_SMALL,
            cursor="hand2",
        )
        chk.pack(anchor="w", pady=(0, 10))

        # Secondary utility buttons
        util_row = tk.Frame(ctrl, bg=BG_PANEL)
        util_row.pack(fill="x")
        util_row.columnconfigure(0, weight=1)
        util_row.columnconfigure(1, weight=1)

        self.btn_chrome = RPGButton(
            util_row,
            text="🌐 Abrir Chrome (S&F)",
            command=self._open_chrome,
            bg="#153247",
            hover_bg="#1f4966",
            pady=8,
        )
        self.btn_chrome.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_tg = RPGButton(
            util_row,
            text="🤖 Configurar Telegram",
            command=self._open_telegram_dialog,
            bg="#153247",
            hover_bg="#1f4966",
            pady=8,
        )
        self.btn_tg.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Live Activity Console card
        log_card = tk.Frame(
            right_panel,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            padx=12,
            pady=10,
        )
        log_card.grid(row=1, column=0, sticky="nsew")

        log_hdr = tk.Frame(log_card, bg=BG_PANEL)
        log_hdr.pack(fill="x", pady=(0, 6))
        tk.Label(
            log_hdr,
            text="REGISTRO EN VIVO",
            font=FONT_SECTION,
            fg=GOLD,
            bg=BG_PANEL,
        ).pack(side="left")

        btn_clear = tk.Label(
            log_hdr,
            text="Limpiar",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL,
            cursor="hand2",
        )
        btn_clear.pack(side="right")
        btn_clear.bind("<Button-1>", lambda _e: self._clear_log())

        log_box_frame = tk.Frame(log_card, bg=BG_INPUT)
        log_box_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_box_frame,
            bg=BG_INPUT,
            fg="#cde2ef",
            insertbackground=GOLD,
            font=FONT_MONO,
            relief="flat",
            wrap="word",
            state="disabled",
            padx=8,
            pady=6,
        )
        log_scroll = tk.Scrollbar(log_box_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        self._append_log("Bienvenido a Shakes & Fortune. Selecciona tu personaje y presiona INICIAR BOT.")

    def _make_stat_tile(self, parent, col: int, title: str, value: str) -> tk.Label:
        frame = tk.Frame(parent, bg=BG_PANEL_INNER)
        frame.grid(row=0, column=col, sticky="ew", padx=4)
        tk.Label(frame, text=title, font=("Segoe UI", 8, "bold"), fg=TEXT_DIM, bg=BG_PANEL_INNER).pack(anchor="w")
        lbl = tk.Label(frame, text=value, font=("Segoe UI", 10, "bold"), fg=TEXT_LIGHT, bg=BG_PANEL_INNER)
        lbl.pack(anchor="w", pady=(2, 0))
        return lbl

    # ------------------------------------------------------------------
    # Roster Rendering & Selection
    # ------------------------------------------------------------------
    def _refresh_roster(self) -> None:
        for w in self.roster_inner.winfo_children():
            w.destroy()
        self.card_widgets.clear()

        profiles = self.config_data.get("profiles", [])
        active_idx = pm.get_active_profile_index(self.config_data)
        self.lbl_roster_count.configure(text=f"{len(profiles)} guardado(s)")

        if not profiles:
            empty = tk.Label(
                self.roster_inner,
                text="Todavía no tenés personajes guardados.\n\nTocá '+ Nuevo' para agregar tu personaje\ny calibrarlo en 1 clic.",
                font=FONT_BODY,
                fg=TEXT_MUTED,
                bg=BG_PANEL_INNER,
                justify="center",
                pady=40,
            )
            empty.pack(fill="both", expand=True)
            self.btn_recal.set_disabled(True)
            self.btn_del_char.set_disabled(True)
            return

        self.btn_recal.set_disabled(False)
        self.btn_del_char.set_disabled(False)

        for idx, prof in enumerate(profiles):
            is_active = idx == active_idx
            card_bg = BG_CARD_ACTIVE if is_active else BG_CARD
            border_col = GOLD if is_active else BORDER_SUBTLE

            card = tk.Frame(
                self.roster_inner,
                bg=card_bg,
                highlightthickness=2 if is_active else 1,
                highlightbackground=border_col,
                padx=12,
                pady=10,
                cursor="hand2",
            )
            card.pack(fill="x", padx=8, pady=(8, 0))

            top = tk.Frame(card, bg=card_bg)
            top.pack(fill="x")

            prefix = "★ " if is_active else "   "
            lbl_name = tk.Label(
                top,
                text=f"{prefix}{prof.get('name', 'Sin nombre')}",
                font=FONT_CARD_TITLE,
                fg=GOLD_BRIGHT if is_active else TEXT_LIGHT,
                bg=card_bg,
                cursor="hand2",
            )
            lbl_name.pack(side="left")

            lbl_srv = tk.Label(
                top,
                text=prof.get("server", "—"),
                font=("Segoe UI", 9, "bold"),
                fg=GOLD if is_active else CYAN,
                bg=BG_PANEL_INNER,
                padx=8,
                pady=2,
                cursor="hand2",
            )
            lbl_srv.pack(side="right")

            rel = prof.get("character_rel", {})
            calibrated = prof.get("calibrated", False)
            status_txt = (
                f"✓ Calibrado ({rel.get('rx', 0):.2f}, {rel.get('ry', 0):.2f})"
                if calibrated
                else "⚠ Sin calibrar — tocá 'Calibrar (1 clic)'"
            )
            lbl_sub = tk.Label(
                card,
                text=status_txt,
                font=FONT_SMALL,
                fg="#7ee2a8" if calibrated else AMBER,
                bg=card_bg,
                cursor="hand2",
            )
            lbl_sub.pack(anchor="w", pady=(4, 0))

            def _bind_select(widget, i=idx):
                widget.bind("<Button-1>", lambda _e: self._select_profile(i))

            for w in (card, top, lbl_name, lbl_srv, lbl_sub):
                _bind_select(w)

            self.card_widgets.append(card)

    def _select_profile(self, index: int) -> None:
        if self._is_bot_running():
            messagebox.showinfo(
                "Bot en ejecución",
                "Detené el bot primero para cambiar de personaje en esta sesión.",
            )
            return
        prof = pm.set_active_profile(self.config_data, index)
        if prof:
            pm.save_config(self.config_data)
            self._refresh_roster()
            self._refresh_summary()
            self._append_log(f"Personaje activo cambiado a: {prof['name']} ({prof['server']})")

    def _refresh_summary(self) -> None:
        profiles = self.config_data.get("profiles", [])
        idx = pm.get_active_profile_index(self.config_data)
        if 0 <= idx < len(profiles):
            p = profiles[idx]
            self.lbl_stat_char.configure(text=f"{p['name']} · {p['server']}", fg=GOLD_BRIGHT)
        else:
            self.lbl_stat_char.configure(text="Sin personaje", fg=AMBER)

        stats = pm.read_bot_stats()
        self.lbl_stat_ads.configure(text=str(stats.get("ads_watched", 0)), fg=TEXT_LIGHT)

        if self.telegram_username:
            self.lbl_stat_tg.configure(text=f"@{self.telegram_username}", fg="#7ee2a8")
        elif pm.has_valid_token_format(self.config_data):
            self.lbl_stat_tg.configure(text="Configurado", fg=CYAN)
        else:
            self.lbl_stat_tg.configure(text="Sin configurar", fg=AMBER)

    # ------------------------------------------------------------------
    # Add / Calibrate / Delete Character Dialogs
    # ------------------------------------------------------------------
    def _open_new_character_dialog(self) -> None:
        if self._is_bot_running():
            messagebox.showinfo("Bot en ejecución", "Detené el bot antes de crear o calibrar un personaje.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Nuevo Personaje")
        dlg.geometry("420x285")
        dlg.configure(bg=BG_PANEL)
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text="⚔  NUEVO PERSONAJE", font=("Georgia", 14, "bold"), fg=GOLD, bg=BG_PANEL).pack(
            anchor="w", padx=20, pady=(16, 4)
        )
        tk.Label(
            dlg,
            text="Elegí un nombre, el servidor y capturá su tarjeta con 1 clic.",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL,
        ).pack(anchor="w", padx=20, pady=(0, 14))

        form = tk.Frame(dlg, bg=BG_PANEL)
        form.pack(fill="x", padx=20)

        tk.Label(form, text="Nombre del personaje", font=FONT_SMALL, fg=TEXT_LIGHT, bg=BG_PANEL).pack(anchor="w")
        ent_name = tk.Entry(
            form,
            bg=BG_INPUT,
            fg=TEXT_LIGHT,
            insertbackground=GOLD,
            font=FONT_BODY,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            highlightcolor=GOLD,
        )
        ent_name.pack(fill="x", ipady=6, pady=(3, 10))
        ent_name.focus_set()

        tk.Label(form, text="Servidor (ej: EU30, EU16, US1, INT1)", font=FONT_SMALL, fg=TEXT_LIGHT, bg=BG_PANEL).pack(
            anchor="w"
        )
        ent_srv = tk.Entry(
            form,
            bg=BG_INPUT,
            fg=TEXT_LIGHT,
            insertbackground=GOLD,
            font=FONT_BODY,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            highlightcolor=GOLD,
        )
        ent_srv.pack(fill="x", ipady=6, pady=(3, 16))

        def _save_and_calibrate():
            name = ent_name.get().strip()
            srv = ent_srv.get().strip().upper()
            if not name:
                messagebox.showwarning("Falta el nombre", "Escribí el nombre del personaje.", parent=dlg)
                return
            if not srv:
                srv = "S&F"
            pm.upsert_profile(self.config_data, name, srv, calibrated=False)
            pm.save_config(self.config_data)
            self._refresh_roster()
            self._refresh_summary()
            dlg.destroy()
            self._start_calibration_for_active()

        def _save_only():
            name = ent_name.get().strip()
            srv = ent_srv.get().strip().upper() or "S&F"
            if not name:
                messagebox.showwarning("Falta el nombre", "Escribí el nombre del personaje.", parent=dlg)
                return
            pm.upsert_profile(self.config_data, name, srv, calibrated=False)
            pm.save_config(self.config_data)
            self._refresh_roster()
            self._refresh_summary()
            dlg.destroy()
            self._append_log(f"Personaje '{name} ({srv})' agregado. Tocá 'Calibrar (1 clic)' para marcar su tarjeta.")

        btn_row = tk.Frame(dlg, bg=BG_PANEL)
        btn_row.pack(fill="x", padx=20)
        RPGButton(
            btn_row,
            text="🎯 Guardar y calibrar ahora",
            command=_save_and_calibrate,
            bg=GREEN,
            hover_bg=GREEN_HOVER,
            border="#52d68a",
            pady=8,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))
        RPGButton(
            btn_row,
            text="Solo guardar",
            command=_save_only,
            bg="#1a3d52",
            hover_bg="#235370",
            pady=8,
        ).pack(side="right")

    def _recalibrate_selected(self) -> None:
        if self._is_bot_running():
            messagebox.showinfo("Bot en ejecución", "Detené el bot antes de calibrar un personaje.")
            return
        self._start_calibration_for_active()

    def _start_calibration_for_active(self) -> None:
        if self.calibrating:
            return
        idx = pm.get_active_profile_index(self.config_data)
        profiles = self.config_data.get("profiles", [])
        if idx < 0 or idx >= len(profiles):
            messagebox.showwarning("Sin personaje", "Primero creá un personaje con '+ Nuevo'.")
            return

        prof = profiles[idx]
        cdp_url = self.config_data.get("browser", {}).get("cdp_url", pm.DEFAULT_CDP_URL)

        try:
            already_open = pm.ensure_chrome_running(cdp_url)
        except Exception as exc:
            messagebox.showerror("Error con Chrome", str(exc))
            return

        if not already_open or not pm.has_sfgame_tab(cdp_url):
            messagebox.showinfo(
                "Abrí el selector de personaje",
                f"En la ventana de Chrome, iniciá sesión en sfgame.net y dejá visible la tarjeta de "
                f"'{prof['name']} ({prof['server']})'.\n\nCuando la veas en pantalla, tocá Aceptar y luego hacé 1 CLIC sobre la tarjeta.",
            )

        self.calibrating = True
        self.btn_recal.set_disabled(True)
        self._append_log(
            f"[CALIBRACIÓN] Esperando 1 clic en Chrome sobre '{prof['name']} ({prof['server']})'..."
        )

        def worker():
            try:
                rel = asyncio.run(
                    pm.capture_character_click(
                        cdp_url=cdp_url,
                        label=f"{prof['name']} ({prof['server']})",
                    )
                )
                self.after(0, lambda: self._on_calibration_done(idx, rel, None))
            except Exception as exc:
                self.after(0, lambda: self._on_calibration_done(idx, None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_calibration_done(self, idx: int, rel: Optional[dict], error: Optional[str]) -> None:
        self.calibrating = False
        self.btn_recal.set_disabled(False)
        if error or not rel:
            self._append_log(f"[ERROR] Calibración cancelada/fallida: {error}")
            messagebox.showerror("Error de calibración", f"No se pudo capturar el clic:\n{error}")
            return

        profiles = self.config_data.get("profiles", [])
        if 0 <= idx < len(profiles):
            prof = profiles[idx]
            pm.upsert_profile(
                self.config_data,
                prof["name"],
                prof["server"],
                character_rel=rel,
                calibrated=True,
                edit_index=idx,
            )
            pm.save_config(self.config_data)
            self._refresh_roster()
            self._refresh_summary()
            self._append_log(
                f"[OK] '{prof['name']} ({prof['server']})' calibrado en ({rel['rx']}, {rel['ry']}). ¡Funciona en cualquier pantalla!"
            )

    def _delete_selected(self) -> None:
        if self._is_bot_running():
            messagebox.showinfo("Bot en ejecución", "Detené el bot primero.")
            return
        idx = pm.get_active_profile_index(self.config_data)
        profiles = self.config_data.get("profiles", [])
        if idx < 0 or idx >= len(profiles):
            return
        prof = profiles[idx]
        if messagebox.askyesno("Eliminar personaje", f"¿Eliminar '{prof['name']} ({prof['server']})' de la lista?"):
            pm.delete_profile(self.config_data, idx)
            pm.save_config(self.config_data)
            self._refresh_roster()
            self._refresh_summary()
            self._append_log(f"Perfil eliminado: {prof['name']} ({prof['server']})")

    # ------------------------------------------------------------------
    # Telegram Setup Modal
    # ------------------------------------------------------------------
    def _open_telegram_dialog(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Configurar tu Bot de Telegram")
        dlg.geometry("480x340")
        dlg.configure(bg=BG_PANEL)
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text="🤖  TU BOT DE TELEGRAM", font=("Georgia", 14, "bold"), fg=GOLD, bg=BG_PANEL).pack(
            anchor="w", padx=20, pady=(16, 4)
        )
        steps_txt = (
            "1. Abrí Telegram y buscá @BotFather\n"
            "2. Mandale /newbot, elegí nombre (ej: Shakes & Fortune) y usuario terminado en 'bot'\n"
            "3. Copiá el TOKEN que te da y pegalo acá abajo\n"
            "4. Al mandar /start por primera vez, tu cuenta queda vinculada automáticamente"
        )
        tk.Label(
            dlg,
            text=steps_txt,
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL_INNER,
            justify="left",
            padx=12,
            pady=10,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
        ).pack(fill="x", padx=20, pady=(6, 12))

        tk.Label(dlg, text="Token de Telegram (@BotFather)", font=FONT_SMALL, fg=TEXT_LIGHT, bg=BG_PANEL).pack(
            anchor="w", padx=20
        )
        ent_token = tk.Entry(
            dlg,
            bg=BG_INPUT,
            fg=TEXT_LIGHT,
            insertbackground=GOLD,
            font=FONT_MONO,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            highlightcolor=GOLD,
        )
        ent_token.pack(fill="x", padx=20, ipady=7, pady=(4, 6))

        existing = str(self.config_data.get("telegram_token", "")).strip()
        if existing and "PON_TU_TOKEN" not in existing:
            ent_token.insert(0, existing)

        lbl_status = tk.Label(dlg, text="", font=FONT_SMALL, fg=CYAN, bg=BG_PANEL)
        lbl_status.pack(anchor="w", padx=20, pady=(2, 10))

        def _validate_and_save():
            token = ent_token.get().strip()
            lbl_status.configure(text="Verificando token con Telegram...", fg=CYAN)
            dlg.update_idletasks()

            def worker():
                info = pm.validate_telegram_token(token)
                self.after(0, lambda: _finish(token, info))

            threading.Thread(target=worker, daemon=True).start()

        def _finish(token: str, info: Optional[dict]):
            if not info:
                lbl_status.configure(text="❌ Token inválido o sin conexión. Revisalo e intentá de nuevo.", fg=RED_HOVER)
                return

            if token != str(self.config_data.get("telegram_token", "")).strip():
                self.config_data["owner_chat_id"] = 0
            self.config_data["telegram_token"] = token
            pm.save_config(self.config_data)
            self.telegram_username = info.get("username")
            self._refresh_summary()
            self._append_log(f"[OK] Bot de Telegram vinculado: @{self.telegram_username}")
            dlg.destroy()

        RPGButton(
            dlg,
            text="✓ Validar y guardar token",
            command=_validate_and_save,
            bg=GREEN,
            hover_bg=GREEN_HOVER,
            border="#52d68a",
            pady=9,
        ).pack(fill="x", padx=20)

    def _check_telegram_async(self) -> None:
        if not pm.has_valid_token_format(self.config_data):
            return
        token = str(self.config_data.get("telegram_token", "")).strip()

        def worker():
            info = pm.validate_telegram_token(token)
            if info:
                self.telegram_username = info.get("username")
                self.after(0, self._refresh_summary)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Chrome & Bot Process Control
    # ------------------------------------------------------------------
    def _open_chrome(self) -> None:
        cdp_url = self.config_data.get("browser", {}).get("cdp_url", pm.DEFAULT_CDP_URL)
        try:
            already = pm.ensure_chrome_running(cdp_url)
            if already:
                self._append_log("[OK] Chrome ya está abierto en el puerto 9222 — se reutilizará esa ventana.")
            else:
                self._append_log("[INFO] Chrome abierto en sfgame.net. Iniciá sesión y dejá el juego cargado.")
        except Exception as exc:
            messagebox.showerror("Error abriendo Chrome", str(exc))

    def _is_bot_running(self) -> bool:
        return self.bot_proc is not None and self.bot_proc.poll() is None

    def _toggle_bot(self) -> None:
        if self._is_bot_running():
            self._stop_bot()
        else:
            self._start_bot()

    def _start_bot(self) -> None:
        if not pm.has_valid_token_format(self.config_data):
            messagebox.showinfo(
                "Falta configurar Telegram",
                "Primero vinculá tu propio bot de Telegram (tarda 30 segundos con @BotFather).",
            )
            self._open_telegram_dialog()
            return

        if not self.config_data.get("profiles"):
            messagebox.showinfo(
                "Falta elegir personaje",
                "Primero agregá y calibrá tu personaje con '+ Nuevo'.",
            )
            self._open_new_character_dialog()
            return

        cdp_url = self.config_data.get("browser", {}).get("cdp_url", pm.DEFAULT_CDP_URL)
        if not pm.is_cdp_ready(cdp_url):
            if messagebox.askyesno(
                "Chrome no detectado",
                "No se detectó Chrome abierto en el puerto 9222.\n\n¿Querés abrirlo ahora en sfgame.net?",
            ):
                self._open_chrome()
            return

        pm.sync_active_profile(self.config_data)
        pm.save_config(self.config_data)

        # Prefer python.exe over pythonw.exe so stdout/stderr pipe streaming is always reliable
        py_exe = sys.executable
        if py_exe.lower().endswith("pythonw.exe"):
            candidate = py_exe[:-11] + "python.exe"
            if os.path.exists(candidate):
                py_exe = candidate

        cmd = [py_exe, "-u", "main.py"]
        if self.autostart_var.get():
            cmd.append("--autostart")

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            self.bot_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                env=env,
            )
        except Exception as exc:
            messagebox.showerror("Error al iniciar el bot", str(exc))
            return

        self.btn_play.set_style(
            text="■  DETENER BOT",
            bg=RED,
            hover_bg=RED_HOVER,
            border="#f2746b",
        )
        self.pill_bot.configure(text="● Bot: Corriendo", fg="#7ee2a8", highlightbackground=GREEN)
        self._append_log(
            f"=== Bot iniciado para {self.config_data.get('character_name')} ({self.config_data.get('server_id')}) ==="
        )

        threading.Thread(target=self._stream_process_output, args=(self.bot_proc,), daemon=True).start()

    def _stream_process_output(self, proc: subprocess.Popen) -> None:
        if proc.stdout:
            for line in proc.stdout:
                self.log_queue.put(line.rstrip())
        code = proc.wait()
        self.log_queue.put(f"=== Bot detenido (código {code}) ===")
        self.after(0, self._on_bot_exited)

    def _stop_bot(self) -> None:
        if not self._is_bot_running():
            return
        self._append_log("Deteniendo bot...")
        try:
            self.bot_proc.terminate()
            try:
                self.bot_proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.bot_proc.kill()
        except Exception:
            pass
        self._on_bot_exited()

    def _on_bot_exited(self) -> None:
        self.btn_play.set_style(
            text="▶  INICIAR BOT",
            bg=GREEN,
            hover_bg=GREEN_HOVER,
            border="#52d68a",
        )
        self.pill_bot.configure(text="● Bot: Detenido", fg=TEXT_MUTED, highlightbackground=BORDER_SUBTLE)

    # ------------------------------------------------------------------
    # Periodic Polling & Logging
    # ------------------------------------------------------------------
    def _poll_status(self) -> None:
        cdp_url = self.config_data.get("browser", {}).get("cdp_url", pm.DEFAULT_CDP_URL)

        def check_chrome():
            ready = pm.is_cdp_ready(cdp_url)
            has_tab = pm.has_sfgame_tab(cdp_url) if ready else False
            self.after(0, lambda: self._update_chrome_pill(ready, has_tab))

        threading.Thread(target=check_chrome, daemon=True).start()
        self._refresh_summary()
        self.after(3000, self._poll_status)

    def _update_chrome_pill(self, ready: bool, has_tab: bool) -> None:
        if ready and has_tab:
            self.pill_chrome.configure(text="● Chrome: sfgame.net listo", fg="#7ee2a8", highlightbackground=GREEN)
        elif ready:
            self.pill_chrome.configure(text="● Chrome: Abre sfgame.net", fg=AMBER, highlightbackground=AMBER)
        else:
            self.pill_chrome.configure(text="● Chrome: No abierto", fg=TEXT_MUTED, highlightbackground=BORDER_SUBTLE)

    def _drain_logs(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(line)
        self.after(150, self._drain_logs)

    def _append_log(self, msg: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        if self._is_bot_running():
            self._stop_bot()
        self.destroy()


def main() -> None:
    app = ShakesFortuneApp()
    app.mainloop()


if __name__ == "__main__":
    main()
