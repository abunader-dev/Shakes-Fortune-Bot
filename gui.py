"""
Shakes & Fortune — Refined RPG Main Menu Launcher.

Features:
  - Custom antialiased 4-leaf clover emblem & Windows native dark titlebar
  - Multi-character roster cards with monogram crest, server pill, and gold active highlight
  - Zero technical jargon — human-friendly, color-coded live activity feed
  - Built-in 1-click @shakes_fortune_bot pairing modal + 1-click character calibration
"""
import asyncio
import ctypes
import datetime
import math
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Optional
import webbrowser

from PIL import Image, ImageDraw, ImageTk

import profile_manager as pm

# Crisp HiDPI rendering on Windows
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# ---- Palette: Obsidian Tavern + Antique Gold + Clover Emerald ----
BG_ABYSS = "#07111a"
BG_PANEL = "#0c1b29"
BG_SURFACE = "#091520"
BG_CARD = "#102436"
BG_CARD_HOVER = "#153047"
BG_CARD_ACTIVE = "#16354e"
BG_INPUT = "#07131e"

GOLD = "#e8b948"
GOLD_BRIGHT = "#ffe07d"
GOLD_DIM = "#6e5620"
BORDER_SUBTLE = "#1a3349"

TEXT_LIGHT = "#eef6fc"
TEXT_SOFT = "#a9c3d6"
TEXT_MUTED = "#6d8da5"
TEXT_DIM = "#4a6880"

EMERALD = "#1fa454"
EMERALD_HOVER = "#26bf63"
EMERALD_SOFT = "#6ee7a0"
EMERALD_BORDER = "#3bd478"

CRIMSON = "#b5332a"
CRIMSON_HOVER = "#d43e34"
CRIMSON_BORDER = "#eb6a61"

SLATE_BTN = "#152d42"
SLATE_BTN_HOVER = "#1d3d59"
AMBER = "#f0a830"
SKY = "#52c4ff"

FONT_TITLE = ("Georgia", 20, "bold")
FONT_SUBTITLE = ("Segoe UI", 9)
FONT_SECTION = ("Segoe UI", 9, "bold")
FONT_CARD_NAME = ("Segoe UI", 11, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TINY = ("Segoe UI", 8, "bold")
FONT_BTN_HERO = ("Segoe UI", 12, "bold")
FONT_BTN = ("Segoe UI", 9, "bold")
FONT_FEED = ("Segoe UI", 9)
FONT_FEED_TIME = ("Consolas", 8)


def _enable_dark_titlebar(window: tk.Misc) -> None:
    """Apply native Windows 10/11 dark titlebar styling when available."""
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        val = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (Win11 / Win10)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)
            )
    except Exception:
        pass


def create_clover_image(size: int = 64) -> Image.Image:
    """Render an antialiased 4-leaf clover medallion emblem using 4x supersampling."""
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = int(s * 0.05)
    # Dark obsidian coin medallion with warm gold rim
    draw.ellipse((pad, pad, s - pad, s - pad), fill=(11, 27, 41, 255), outline=(232, 185, 72, 255), width=max(2, s // 26))
    inner = pad + max(3, s // 20)
    draw.ellipse((inner, inner, s - inner, s - inner), outline=(110, 86, 32, 180), width=max(1, s // 64))

    cx, cy = s * 0.5, s * 0.48

    # Curved stem
    stem_pts = [
        (cx, cy + s * 0.04),
        (cx + s * 0.02, cy + s * 0.22),
        (cx + s * 0.09, cy + s * 0.34),
    ]
    draw.line(stem_pts, fill=(24, 148, 72, 255), width=max(3, s // 22), joint="curve")

    # Four symmetrical clover leaves (each leaf built from two slightly offset lobes)
    leaf_dist = s * 0.165
    lobe_r = s * 0.125
    lobe_spread = 0.38  # radians

    for angle_deg in (-135, -45, 45, 135):
        base_rad = math.radians(angle_deg)
        # Main leaf shadow/body
        for delta in (-lobe_spread, lobe_spread):
            lx = cx + math.cos(base_rad + delta) * leaf_dist
            ly = cy + math.sin(base_rad + delta) * leaf_dist
            draw.ellipse(
                (lx - lobe_r, ly - lobe_r, lx + lobe_r, ly + lobe_r),
                fill=(26, 168, 82, 255),
            )
        # Inner bridge toward center
        bx = cx + math.cos(base_rad) * (leaf_dist * 0.55)
        by = cy + math.sin(base_rad) * (leaf_dist * 0.55)
        br = lobe_r * 0.85
        draw.ellipse((bx - br, by - br, bx + br, by + br), fill=(26, 168, 82, 255))

        # Bright emerald highlight inside each leaf
        hx = cx + math.cos(base_rad - 0.12) * (leaf_dist * 0.92)
        hy = cy + math.sin(base_rad - 0.12) * (leaf_dist * 0.92)
        hr = lobe_r * 0.52
        draw.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=(58, 214, 114, 210))

    # Tiny center vein dot
    cr = s * 0.045
    draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=(18, 128, 62, 255))

    return img.resize((size, size), Image.Resampling.LANCZOS)


def format_activity_line(raw: str) -> Optional[tuple[str, str]]:
    """Convert raw bot logs into clean, friendly activity items: (text, tag) or None to hide."""
    line = raw.strip()
    if not line:
        return None

    low = line.lower()

    # Hide noisy/technical internals
    ignore_patterns = (
        "traceback",
        "file \"",
        "httpx",
        "apscheduler",
        "starting in relay mode",
        "connected to shakes & fortune relay",
        "starting run_sf_bot",
        "connecting to the user-managed chrome",
        "an active character session is already open",
        "clicked ad close button via dom",
        "closing ad modal",
        "video paused at 0s",
        "application started",
        "disconnected from the user-managed",
        "run_sf_bot task was cancelled",
        "relay loop cancelled",
        "post_shutdown",
        "waiting for commands",
    )
    if any(p in low for p in ignore_patterns):
        return None

    if "selecting " in low and "through the game canvas" in low:
        return ("🧙  Ingresando con tu personaje...", "gold")
    if "character session confirmed" in low:
        return ("✓  Sesión del personaje confirmada", "ok")
    if "character selection is still visible" in low:
        return ("⚠  No se pudo entrar al personaje — revisa la calibración", "warn")
    if "navigating to wheel" in low:
        return ("🎡  Abriendo la Ruleta de Dr. Abawuwu...", "info")
    if "waiting for flying tv" in low:
        return ("📺  Buscando la TV Voladora...", "info")
    if "ad started after" in low:
        return ("🎬  Anuncio detectado — reproduciendo video...", "sky")
    if "waiting for ad end" in low:
        return None
    if "'reward granted' confirmed" in low:
        return ("✨  ¡Recompensa confirmada! Cerrando anuncio...", "gold")
    if "ad modal closed successfully" in low:
        return ("🍀  Anuncio cerrado limpiamente", "ok")
    if "ad watched successfully! total:" in low:
        m = re.search(r"total:\s*(\d+)", low)
        total = m.group(1) if m else ""
        return (f"🏆  ¡Ciclo completado! Total de anuncios: {total}", "gold_bold")
    if "closed ad popup tab" in low:
        return ("🛡  Ventana emergente bloqueada automáticamente", "muted")
    if "received /start" in low:
        return ("📱  Inicio activado desde Telegram", "sky")
    if "received /stop" in low:
        return ("📱  Pausa solicitada desde Telegram", "warn")
    if "received /status" in low:
        return ("📱  Reporte de estado enviado a Telegram", "info")
    if "session drop" in low or "character selection detected" in low:
        return ("🔄  El juego cerró sesión — reconectando automáticamente...", "warn")
    if "3 consecutive session drops" in low:
        return ("⛔  Detenido tras 3 desconexiones seguidas", "err")
    if "5 consecutive" in low or "5 errores" in low:
        return ("⛔  Detenido tras varios reintentos fallidos", "err")
    if "open sfgame.net in chrome" in low:
        return ("⚠  Abre sfgame.net en el navegador antes de iniciar", "warn")
    if "unlinked in telegram" in low:
        return ("⚠  Esta PC fue desvinculada en Telegram — vuelve a vincularla", "warn")
    if "flying tv did not appear" in low:
        return ("⏳  La TV Voladora no apareció todavía — reintentando...", "muted")
    if "cycle failed" in low or "error" in low:
        return ("⏳  Ocurrió un imprevisto — reintentando ciclo...", "warn")

    return None


class RPGButton(tk.Label):
    """Crisp flat button with smooth hover highlight and disabled state."""

    def __init__(
        self,
        parent,
        text: str,
        command,
        *,
        bg: str = SLATE_BTN,
        hover_bg: str = SLATE_BTN_HOVER,
        fg: str = TEXT_LIGHT,
        border: str = BORDER_SUBTLE,
        hover_border: str = GOLD,
        font=FONT_BTN,
        padx: int = 14,
        pady: int = 8,
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
            highlightcolor=hover_border,
            **kwargs,
        )
        self._bg = bg
        self._hover_bg = hover_bg
        self._fg = fg
        self._border = border
        self._hover_border = hover_border
        self._command = command
        self._disabled = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _e):
        if not self._disabled:
            self.configure(bg=self._hover_bg, highlightbackground=self._hover_border)

    def _on_leave(self, _e):
        if not self._disabled:
            self.configure(bg=self._bg, highlightbackground=self._border)

    def _on_click(self, _e):
        if not self._disabled and self._command:
            self._command()

    def set_style(
        self,
        *,
        text: Optional[str] = None,
        bg: Optional[str] = None,
        hover_bg: Optional[str] = None,
        border: Optional[str] = None,
        hover_border: Optional[str] = None,
    ):
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
        if hover_border is not None:
            self._hover_border = hover_border

    def set_disabled(self, disabled: bool):
        self._disabled = disabled
        self.configure(
            cursor="arrow" if disabled else "hand2",
            fg=TEXT_DIM if disabled else self._fg,
            bg="#0b1824" if disabled else self._bg,
            highlightbackground="#132638" if disabled else self._border,
        )


class ShakesFortuneApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Shakes & Fortune 🍀")
        self.geometry("980x670")
        self.minsize(900, 610)
        self.configure(bg=BG_ABYSS)

        # Custom 4-leaf clover window icon (replaces the default Tk feather)
        self._icon_img = ImageTk.PhotoImage(create_clover_image(64))
        self._header_logo = ImageTk.PhotoImage(create_clover_image(46))
        self.iconphoto(True, self._icon_img)
        _enable_dark_titlebar(self)

        self.config_data = pm.load_config()
        self.bot_proc: Optional[subprocess.Popen] = None
        self.event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.calibrating = False
        self.autostart_var = tk.BooleanVar(value=True)
        self.card_widgets: list[tk.Frame] = []

        self._build_ui()
        self._refresh_roster()
        self._refresh_summary()
        self._poll_status()
        self._drain_events()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI Layout
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # Thin decorative gold accent bar across the very top
        tk.Frame(self, bg=GOLD, height=2).pack(fill="x")

        # ---- Header Banner ----
        header = tk.Frame(
            self,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground=GOLD_DIM,
            padx=22,
            pady=14,
        )
        header.pack(fill="x", padx=18, pady=(14, 12))

        brand = tk.Frame(header, bg=BG_PANEL)
        brand.pack(side="left")

        tk.Label(brand, image=self._header_logo, bg=BG_PANEL).pack(side="left", padx=(0, 14))

        title_stack = tk.Frame(brand, bg=BG_PANEL)
        title_stack.pack(side="left")

        tk.Label(
            title_stack,
            text="Shakes & Fortune 🍀",
            font=FONT_TITLE,
            fg=GOLD_BRIGHT,
            bg=BG_PANEL,
        ).pack(anchor="w")

        tk.Label(
            title_stack,
            text="Dr. Abawuwu Lucky Coin Auto Farmer",
            font=FONT_SUBTITLE,
            fg=TEXT_SOFT,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(1, 0))

        # Status pills (clean, non-technical)
        pills = tk.Frame(header, bg=BG_PANEL)
        pills.pack(side="right")

        self.pill_game = tk.Label(
            pills,
            text="● Comprobando juego...",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_SURFACE,
            padx=12,
            pady=6,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
        )
        self.pill_game.pack(side="left", padx=(0, 8))

        self.pill_bot = tk.Label(
            pills,
            text="● En pausa",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_SURFACE,
            padx=12,
            pady=6,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
        )
        self.pill_bot.pack(side="left")

        # ---- Main Two-Column Content ----
        body = tk.Frame(self, bg=BG_ABYSS)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=7)
        body.rowconfigure(0, weight=1)

        # LEFT PANEL: Character Roster
        left_panel = tk.Frame(
            body,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground=GOLD_DIM,
            padx=16,
            pady=14,
        )
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        roster_hdr = tk.Frame(left_panel, bg=BG_PANEL)
        roster_hdr.pack(fill="x", pady=(0, 10))
        tk.Label(
            roster_hdr,
            text="PERSONAJES",
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

        # Scrollable roster area
        roster_wrap = tk.Frame(
            left_panel,
            bg=BG_SURFACE,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
        )
        roster_wrap.pack(fill="both", expand=True)

        self.roster_canvas = tk.Canvas(
            roster_wrap,
            bg=BG_SURFACE,
            highlightthickness=0,
        )
        roster_scroll = tk.Scrollbar(
            roster_wrap,
            orient="vertical",
            command=self.roster_canvas.yview,
        )
        self.roster_inner = tk.Frame(self.roster_canvas, bg=BG_SURFACE)
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
        self.roster_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self._on_mousewheel(e),
        )
        self.roster_canvas.configure(yscrollcommand=roster_scroll.set)
        self.roster_canvas.pack(side="left", fill="both", expand=True)
        roster_scroll.pack(side="right", fill="y")

        # Roster action buttons
        roster_btns = tk.Frame(left_panel, bg=BG_PANEL)
        roster_btns.pack(fill="x", pady=(12, 0))

        self.btn_add_char = RPGButton(
            roster_btns,
            text="+ Nuevo",
            command=self._open_new_character_dialog,
            bg=SLATE_BTN,
            hover_bg=SLATE_BTN_HOVER,
            border=GOLD_DIM,
            padx=12,
            pady=7,
        )
        self.btn_add_char.pack(side="left", padx=(0, 6))

        self.btn_recal = RPGButton(
            roster_btns,
            text="🎯 Calibrar",
            command=self._recalibrate_selected,
            bg=SLATE_BTN,
            hover_bg=SLATE_BTN_HOVER,
            padx=12,
            pady=7,
        )
        self.btn_recal.pack(side="left", padx=(0, 6))

        self.btn_del_char = RPGButton(
            roster_btns,
            text="Eliminar",
            command=self._delete_selected,
            bg="#2b1417",
            hover_bg=CRIMSON,
            border="#57262b",
            hover_border=CRIMSON_BORDER,
            padx=10,
            pady=7,
        )
        self.btn_del_char.pack(side="right")

        # RIGHT COLUMN: Control Card + Stylized Activity Feed
        right_col = tk.Frame(body, bg=BG_ABYSS)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right_col.rowconfigure(1, weight=1)
        right_col.columnconfigure(0, weight=1)

        # Control Card
        ctrl = tk.Frame(
            right_col,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground=GOLD_DIM,
            padx=18,
            pady=16,
        )
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        tk.Label(
            ctrl,
            text="PANEL DE CONTROL",
            font=FONT_SECTION,
            fg=GOLD,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(0, 10))

        # 3 Elevated Stat Tiles
        stats = tk.Frame(ctrl, bg=BG_PANEL)
        stats.pack(fill="x", pady=(0, 14))
        stats.columnconfigure(0, weight=1)
        stats.columnconfigure(1, weight=1)
        stats.columnconfigure(2, weight=1)

        self.lbl_stat_char = self._make_stat_card(stats, 0, "PERSONAJE ACTIVO", "—", GOLD_BRIGHT)
        self.lbl_stat_ads = self._make_stat_card(stats, 1, "ANUNCIOS VISTOS", "0", EMERALD_SOFT)
        self.lbl_stat_tg = self._make_stat_card(stats, 2, "TELEGRAM", "Sin vincular", AMBER)

        # Hero Play / Stop CTA
        self.btn_play = RPGButton(
            ctrl,
            text="▶  INICIAR FARMEO",
            command=self._toggle_bot,
            bg=EMERALD,
            hover_bg=EMERALD_HOVER,
            border=EMERALD_BORDER,
            hover_border="#9bf0be",
            font=FONT_BTN_HERO,
            pady=13,
        )
        self.btn_play.pack(fill="x", pady=(0, 8))

        chk = tk.Checkbutton(
            ctrl,
            text="Empezar de inmediato al iniciar (también puedes controlarlo desde Telegram)",
            variable=self.autostart_var,
            bg=BG_PANEL,
            fg=TEXT_MUTED,
            selectcolor=BG_INPUT,
            activebackground=BG_PANEL,
            activeforeground=TEXT_LIGHT,
            font=FONT_SMALL,
            cursor="hand2",
        )
        chk.pack(anchor="w", pady=(0, 12))

        # Utility Buttons Row
        util_row = tk.Frame(ctrl, bg=BG_PANEL)
        util_row.pack(fill="x")
        util_row.columnconfigure(0, weight=1)
        util_row.columnconfigure(1, weight=1)

        self.btn_chrome = RPGButton(
            util_row,
            text="🌐  Abrir el juego",
            command=self._open_chrome,
            bg=SLATE_BTN,
            hover_bg=SLATE_BTN_HOVER,
            pady=9,
        )
        self.btn_chrome.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_tg = RPGButton(
            util_row,
            text="🍀  Vincular Telegram",
            command=self._open_telegram_dialog,
            bg=SLATE_BTN,
            hover_bg=SLATE_BTN_HOVER,
            pady=9,
        )
        self.btn_tg.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Stylized Live Activity Feed
        feed_card = tk.Frame(
            right_col,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            padx=16,
            pady=12,
        )
        feed_card.grid(row=1, column=0, sticky="nsew")

        feed_hdr = tk.Frame(feed_card, bg=BG_PANEL)
        feed_hdr.pack(fill="x", pady=(0, 8))
        tk.Label(
            feed_hdr,
            text="ACTIVIDAD RECIENTE",
            font=FONT_SECTION,
            fg=GOLD,
            bg=BG_PANEL,
        ).pack(side="left")

        btn_clear = tk.Label(
            feed_hdr,
            text="Limpiar",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL,
            cursor="hand2",
        )
        btn_clear.pack(side="right")
        btn_clear.bind("<Enter>", lambda _e: btn_clear.configure(fg=GOLD_BRIGHT))
        btn_clear.bind("<Leave>", lambda _e: btn_clear.configure(fg=TEXT_MUTED))
        btn_clear.bind("<Button-1>", lambda _e: self._clear_feed())

        feed_wrap = tk.Frame(
            feed_card,
            bg=BG_SURFACE,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
        )
        feed_wrap.pack(fill="both", expand=True)

        self.feed_text = tk.Text(
            feed_wrap,
            bg=BG_SURFACE,
            fg=TEXT_SOFT,
            font=FONT_FEED,
            relief="flat",
            wrap="word",
            state="disabled",
            padx=12,
            pady=10,
            spacing1=3,
            spacing3=4,
            cursor="arrow",
        )
        feed_scroll = tk.Scrollbar(feed_wrap, command=self.feed_text.yview)
        self.feed_text.configure(yscrollcommand=feed_scroll.set)
        self.feed_text.pack(side="left", fill="both", expand=True)
        feed_scroll.pack(side="right", fill="y")

        # Color tags for clean event styling
        self.feed_text.tag_configure("time", foreground=TEXT_DIM, font=FONT_FEED_TIME)
        self.feed_text.tag_configure("info", foreground=TEXT_SOFT)
        self.feed_text.tag_configure("ok", foreground=EMERALD_SOFT)
        self.feed_text.tag_configure("sky", foreground=SKY)
        self.feed_text.tag_configure("gold", foreground=GOLD_BRIGHT)
        self.feed_text.tag_configure("gold_bold", foreground=GOLD_BRIGHT, font=("Segoe UI", 9, "bold"))
        self.feed_text.tag_configure("warn", foreground=AMBER)
        self.feed_text.tag_configure("err", foreground="#ff7b72")
        self.feed_text.tag_configure("muted", foreground=TEXT_MUTED)

        self._push_event("🍀  Listo para empezar. Elige tu personaje y presiona INICIAR FARMEO.", "gold")

    def _make_stat_card(self, parent, col: int, title: str, value: str, color: str) -> tk.Label:
        padx = (0, 6) if col == 0 else ((6, 0) if col == 2 else (3, 3))
        card = tk.Frame(
            parent,
            bg=BG_SURFACE,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            padx=12,
            pady=9,
        )
        card.grid(row=0, column=col, sticky="ew", padx=padx)
        tk.Label(card, text=title, font=FONT_TINY, fg=TEXT_DIM, bg=BG_SURFACE).pack(anchor="w")
        lbl = tk.Label(card, text=value, font=("Segoe UI", 11, "bold"), fg=color, bg=BG_SURFACE)
        lbl.pack(anchor="w", pady=(3, 0))
        return lbl

    def _on_mousewheel(self, event) -> None:
        # Scroll roster only when pointer is over the roster canvas
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget and str(widget).startswith(str(self.roster_canvas)):
            self.roster_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Character Roster Cards
    # ------------------------------------------------------------------
    def _refresh_roster(self) -> None:
        for w in self.roster_inner.winfo_children():
            w.destroy()
        self.card_widgets.clear()

        profiles = self.config_data.get("profiles", [])
        active_idx = pm.get_active_profile_index(self.config_data)
        self.lbl_roster_count.configure(
            text=f"{len(profiles)} personaje" + ("" if len(profiles) == 1 else "s")
        )

        if not profiles:
            tk.Label(
                self.roster_inner,
                text="Aún no tienes personajes guardados.\n\nHaz clic en '+ Nuevo' para agregar\ntu personaje y calibrarlo en 1 clic.",
                font=FONT_BODY,
                fg=TEXT_MUTED,
                bg=BG_SURFACE,
                justify="center",
                pady=46,
            ).pack(fill="both", expand=True)
            self.btn_recal.set_disabled(True)
            self.btn_del_char.set_disabled(True)
            return

        self.btn_recal.set_disabled(False)
        self.btn_del_char.set_disabled(False)

        for idx, prof in enumerate(profiles):
            is_active = idx == active_idx
            card_bg = BG_CARD_ACTIVE if is_active else BG_CARD
            border_col = GOLD if is_active else BORDER_SUBTLE

            outer = tk.Frame(
                self.roster_inner,
                bg=card_bg,
                highlightthickness=1,
                highlightbackground=border_col,
                cursor="hand2",
            )
            outer.pack(fill="x", padx=10, pady=(10, 0))

            # Left glowing accent stripe for the active character
            stripe = tk.Frame(outer, bg=GOLD if is_active else "#1d384f", width=4)
            stripe.pack(side="left", fill="y")

            content = tk.Frame(outer, bg=card_bg, padx=12, pady=10)
            content.pack(side="left", fill="both", expand=True)

            # Character monogram badge
            name = prof.get("name", "?")
            initial = name[:1].upper() if name else "?"
            avatar = tk.Label(
                content,
                text=initial,
                font=("Georgia", 13, "bold"),
                fg=BG_ABYSS if is_active else GOLD_BRIGHT,
                bg=GOLD if is_active else "#1a3b57",
                width=2,
                pady=4,
                cursor="hand2",
            )
            avatar.pack(side="left", padx=(0, 12))

            info_col = tk.Frame(content, bg=card_bg)
            info_col.pack(side="left", fill="both", expand=True)

            top_row = tk.Frame(info_col, bg=card_bg)
            top_row.pack(fill="x")

            lbl_name = tk.Label(
                top_row,
                text=name,
                font=FONT_CARD_NAME,
                fg=GOLD_BRIGHT if is_active else TEXT_LIGHT,
                bg=card_bg,
                cursor="hand2",
            )
            lbl_name.pack(side="left")

            lbl_srv = tk.Label(
                top_row,
                text=prof.get("server", "S&F"),
                font=FONT_TINY,
                fg=GOLD_BRIGHT if is_active else SKY,
                bg=BG_SURFACE,
                padx=8,
                pady=2,
                cursor="hand2",
            )
            lbl_srv.pack(side="right")

            calibrated = prof.get("calibrated", False)
            badge_txt = "✓ Listo para jugar" if calibrated else "⚠ Falta calibrar (1 clic)"
            lbl_badge = tk.Label(
                info_col,
                text=badge_txt,
                font=FONT_SMALL,
                fg=EMERALD_SOFT if calibrated else AMBER,
                bg=card_bg,
                cursor="hand2",
            )
            lbl_badge.pack(anchor="w", pady=(3, 0))

            clickable = (outer, stripe, content, avatar, info_col, top_row, lbl_name, lbl_srv, lbl_badge)

            def _bind(widgets, i=idx, active=is_active):
                for w in widgets:
                    w.bind("<Button-1>", lambda _e: self._select_profile(i))
                    if not active:
                        w.bind("<Enter>", lambda _e, o=outer: o.configure(highlightbackground=GOLD_DIM))
                        w.bind("<Leave>", lambda _e, o=outer: o.configure(highlightbackground=BORDER_SUBTLE))

            _bind(clickable)
            self.card_widgets.append(outer)

    def _select_profile(self, index: int) -> None:
        if self._is_bot_running():
            messagebox.showinfo(
                "Bot en marcha",
                "Detén el farmeo primero para cambiar de personaje.",
            )
            return
        prof = pm.set_active_profile(self.config_data, index)
        if prof:
            pm.save_config(self.config_data)
            self._refresh_roster()
            self._refresh_summary()
            self._push_event(f"🧙  Personaje seleccionado: {prof['name']} ({prof['server']})", "gold")

    def _refresh_summary(self) -> None:
        profiles = self.config_data.get("profiles", [])
        idx = pm.get_active_profile_index(self.config_data)
        if 0 <= idx < len(profiles):
            p = profiles[idx]
            self.lbl_stat_char.configure(text=f"{p['name']} · {p['server']}", fg=GOLD_BRIGHT)
        else:
            self.lbl_stat_char.configure(text="Sin elegir", fg=AMBER)

        stats = pm.read_bot_stats()
        self.lbl_stat_ads.configure(text=str(stats.get("ads_watched", 0)), fg=EMERALD_SOFT)

        if pm.is_relay_linked(self.config_data):
            tg_user = (self.config_data.get("relay") or {}).get("telegram_user", "")
            label = f"@{tg_user}" if tg_user else "Vinculado"
            self.lbl_stat_tg.configure(text=f"✓ {label}", fg=EMERALD_SOFT)
        else:
            self.lbl_stat_tg.configure(text="Sin vincular", fg=AMBER)

    # ------------------------------------------------------------------
    # Character Creation & 1-Click Calibration
    # ------------------------------------------------------------------
    def _open_new_character_dialog(self) -> None:
        if self._is_bot_running():
            messagebox.showinfo("Bot en marcha", "Detén el bot antes de agregar un personaje.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Nuevo Personaje")
        dlg.geometry("430x295")
        dlg.configure(bg=BG_PANEL)
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        dlg.iconphoto(True, self._icon_img)
        _enable_dark_titlebar(dlg)

        tk.Frame(dlg, bg=GOLD, height=2).pack(fill="x")
        tk.Label(dlg, text="Nuevo Personaje", font=("Georgia", 15, "bold"), fg=GOLD_BRIGHT, bg=BG_PANEL).pack(
            anchor="w", padx=22, pady=(16, 2)
        )
        tk.Label(
            dlg,
            text="Ingresa tu personaje y servidor para añadirlo a tu lista.",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL,
        ).pack(anchor="w", padx=22, pady=(0, 14))

        form = tk.Frame(dlg, bg=BG_PANEL)
        form.pack(fill="x", padx=22)

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
        ent_name.pack(fill="x", ipady=7, pady=(4, 12))
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
        ent_srv.pack(fill="x", ipady=7, pady=(4, 18))

        def _save(calibrate_now: bool):
            name = ent_name.get().strip()
            srv = ent_srv.get().strip().upper() or "S&F"
            if not name:
                messagebox.showwarning("Falta el nombre", "Escribe el nombre de tu personaje.", parent=dlg)
                return
            pm.upsert_profile(self.config_data, name, srv, calibrated=False)
            pm.save_config(self.config_data)
            self._refresh_roster()
            self._refresh_summary()
            dlg.destroy()
            if calibrate_now:
                self._start_calibration_for_active()
            else:
                self._push_event(f"✨  Personaje '{name} ({srv})' guardado.", "info")

        btn_row = tk.Frame(dlg, bg=BG_PANEL)
        btn_row.pack(fill="x", padx=22)
        RPGButton(
            btn_row,
            text="🎯  Guardar y calibrar",
            command=lambda: _save(True),
            bg=EMERALD,
            hover_bg=EMERALD_HOVER,
            border=EMERALD_BORDER,
            pady=9,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))
        RPGButton(
            btn_row,
            text="Solo guardar",
            command=lambda: _save(False),
            bg=SLATE_BTN,
            hover_bg=SLATE_BTN_HOVER,
            pady=9,
        ).pack(side="right")

    def _recalibrate_selected(self) -> None:
        if self._is_bot_running():
            messagebox.showinfo("Bot en marcha", "Detén el bot antes de calibrar un personaje.")
            return
        self._start_calibration_for_active()

    def _start_calibration_for_active(self) -> None:
        if self.calibrating:
            return
        idx = pm.get_active_profile_index(self.config_data)
        profiles = self.config_data.get("profiles", [])
        if idx < 0 or idx >= len(profiles):
            messagebox.showwarning("Sin personaje", "Primero crea un personaje con '+ Nuevo'.")
            return

        prof = profiles[idx]
        cdp_url = self.config_data.get("browser", {}).get("cdp_url", pm.DEFAULT_CDP_URL)

        try:
            already_open = pm.ensure_chrome_running(cdp_url)
        except Exception as exc:
            messagebox.showerror("Navegador no encontrado", str(exc))
            return

        if not already_open or not pm.has_sfgame_tab(cdp_url):
            messagebox.showinfo(
                "Abre la selección de personaje",
                f"En el navegador, inicia sesión en sfgame.net y deja visible la tarjeta de "
                f"'{prof['name']} ({prof['server']})'.\n\nCuando la veas en pantalla, presiona Aceptar y haz 1 clic sobre tu personaje.",
            )

        self.calibrating = True
        self.btn_recal.set_disabled(True)
        self._push_event(f"🎯  Haz 1 clic sobre '{prof['name']} ({prof['server']})' en el juego...", "sky")

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
            self._push_event("⚠  No se completó la calibración. Intenta de nuevo con el juego abierto.", "warn")
            messagebox.showwarning(
                "Calibración pendiente",
                "Asegúrate de tener abierta la pestaña de sfgame.net en la pantalla de Selección de personaje e inténtalo de nuevo.",
            )
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
            self._push_event(f"✓  '{prof['name']} ({prof['server']})' calibrado y listo para jugar.", "ok")

    def _delete_selected(self) -> None:
        if self._is_bot_running():
            messagebox.showinfo("Bot en marcha", "Detén el bot primero.")
            return
        idx = pm.get_active_profile_index(self.config_data)
        profiles = self.config_data.get("profiles", [])
        if idx < 0 or idx >= len(profiles):
            return
        prof = profiles[idx]
        if messagebox.askyesno("Eliminar personaje", f"¿Eliminar '{prof['name']} ({prof['server']})' de tu lista?"):
            pm.delete_profile(self.config_data, idx)
            pm.save_config(self.config_data)
            self._refresh_roster()
            self._refresh_summary()
            self._push_event(f"🗑  Personaje '{prof['name']} ({prof['server']})' eliminado.", "muted")

    # ------------------------------------------------------------------
    # Telegram Pairing Modal (@shakes_fortune_bot)
    # ------------------------------------------------------------------
    def _open_telegram_dialog(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Vincular Telegram — Shakes & Fortune 🍀")
        dlg.geometry("490x400")
        dlg.configure(bg=BG_PANEL)
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        dlg.iconphoto(True, self._icon_img)
        _enable_dark_titlebar(dlg)

        relay_url = pm.get_relay_url(self.config_data)
        state_box = {"closed": False, "code": "", "secret": ""}

        tk.Frame(dlg, bg=GOLD, height=2).pack(fill="x")
        tk.Label(
            dlg,
            text="🍀  Vincular con Telegram",
            font=("Georgia", 15, "bold"),
            fg=GOLD_BRIGHT,
            bg=BG_PANEL,
        ).pack(anchor="w", padx=22, pady=(16, 3))

        tk.Label(
            dlg,
            text=f"Conecta tu computadora con @{pm.BOT_USERNAME} en unos segundos.",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_PANEL,
        ).pack(anchor="w", padx=22, pady=(0, 14))

        code_card = tk.Frame(
            dlg,
            bg=BG_SURFACE,
            highlightthickness=1,
            highlightbackground=GOLD_DIM,
            padx=16,
            pady=16,
        )
        code_card.pack(fill="x", padx=22, pady=(0, 12))

        tk.Label(
            code_card,
            text="TU CÓDIGO DE VINCULACIÓN",
            font=FONT_TINY,
            fg=TEXT_DIM,
            bg=BG_SURFACE,
        ).pack()

        lbl_code = tk.Label(
            code_card,
            text="••• •••",
            font=("Consolas", 28, "bold"),
            fg=GOLD_BRIGHT,
            bg=BG_SURFACE,
            pady=6,
        )
        lbl_code.pack()

        lbl_hint = tk.Label(
            code_card,
            text=f"Busca @{pm.BOT_USERNAME} en Telegram y envía /vincular CODIGO",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_SURFACE,
        )
        lbl_hint.pack()

        lbl_status = tk.Label(
            dlg,
            text="⏳  Preparando código...",
            font=FONT_SMALL,
            fg=SKY,
            bg=BG_PANEL,
        )
        lbl_status.pack(pady=(0, 12))

        def _open_deeplink():
            code = state_box["code"]
            if code:
                webbrowser.open(f"https://t.me/{pm.BOT_USERNAME}?start={code}")

        def _copy_cmd():
            code = state_box["code"]
            if code:
                self.clipboard_clear()
                self.clipboard_append(f"/vincular {code}")
                lbl_status.configure(
                    text=f"📋  Copiado: /vincular {code} — pégalo en @{pm.BOT_USERNAME}",
                    fg=GOLD_BRIGHT,
                )

        btn_open = RPGButton(
            dlg,
            text=f"🍀  Abrir @{pm.BOT_USERNAME} en Telegram",
            command=_open_deeplink,
            bg=EMERALD,
            hover_bg=EMERALD_HOVER,
            border=EMERALD_BORDER,
            font=FONT_BTN,
            pady=10,
        )
        btn_open.pack(fill="x", padx=22, pady=(0, 8))
        btn_open.set_disabled(True)

        btn_copy = RPGButton(
            dlg,
            text="📋  Copiar comando /vincular",
            command=_copy_cmd,
            bg=SLATE_BTN,
            hover_bg=SLATE_BTN_HOVER,
            pady=8,
        )
        btn_copy.pack(fill="x", padx=22)
        btn_copy.set_disabled(True)

        def _on_close_dlg():
            state_box["closed"] = True
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", _on_close_dlg)

        def _request_code():
            try:
                data = pm.relay_create_pair(relay_url)
                state_box["code"] = str(data["code"])
                state_box["secret"] = str(data["secret"])
                self.after(0, lambda: _on_code_ready(state_box["code"]))
            except Exception:
                self.after(0, _on_code_error)

        def _on_code_ready(code: str):
            if state_box["closed"]:
                return
            lbl_code.configure(text=f"{code[:3]} {code[3:]}")
            lbl_hint.configure(text=f"En @{pm.BOT_USERNAME} envía:  /vincular {code}")
            lbl_status.configure(text="⏳  Esperando tu confirmación en Telegram...", fg=SKY)
            btn_open.set_disabled(False)
            btn_copy.set_disabled(False)
            _schedule_poll()

        def _on_code_error():
            if state_box["closed"]:
                return
            lbl_code.configure(text="SIN CONEXIÓN", font=("Segoe UI", 16, "bold"), fg="#ff7b72")
            lbl_status.configure(text="⚠  Verifica tu conexión a internet e intenta de nuevo.", fg=AMBER)

        def _schedule_poll():
            if state_box["closed"]:
                return

            def worker():
                try:
                    res = pm.relay_check_pair_status(relay_url, state_box["secret"])
                    if res.get("linked"):
                        self.after(0, lambda: _on_linked(res))
                        return
                except Exception:
                    pass
                if not state_box["closed"]:
                    self.after(2000, _schedule_poll)

            threading.Thread(target=worker, daemon=True).start()

        def _on_linked(res: dict):
            if state_box["closed"]:
                return
            relay_cfg = self.config_data.setdefault("relay", {})
            relay_cfg["url"] = relay_url
            relay_cfg["client_secret"] = state_box["secret"]
            relay_cfg["telegram_user"] = res.get("username") or res.get("first_name") or ""
            pm.save_config(self.config_data)
            self._refresh_summary()
            self._push_event(f"🍀  Telegram vinculado correctamente con @{pm.BOT_USERNAME}.", "ok")
            lbl_status.configure(text="✅  ¡Vinculado con éxito!", fg=EMERALD_SOFT)
            self.after(900, _on_close_dlg)

        threading.Thread(target=_request_code, daemon=True).start()

    # ------------------------------------------------------------------
    # Browser & Bot Lifecycle
    # ------------------------------------------------------------------
    def _open_chrome(self) -> None:
        cdp_url = self.config_data.get("browser", {}).get("cdp_url", pm.DEFAULT_CDP_URL)
        try:
            already = pm.ensure_chrome_running(cdp_url)
            if already:
                self._push_event("✓  El navegador del juego ya está abierto y listo.", "ok")
            else:
                self._push_event("🌐  Abriendo Shakes & Fidget en el navegador...", "sky")
        except Exception:
            messagebox.showerror("Navegador no encontrado", "Instala Google Chrome para usar Shakes & Fortune.")

    def _is_bot_running(self) -> bool:
        return self.bot_proc is not None and self.bot_proc.poll() is None

    def _toggle_bot(self) -> None:
        if self._is_bot_running():
            self._stop_bot()
        else:
            self._start_bot()

    def _start_bot(self) -> None:
        if not pm.is_relay_linked(self.config_data):
            messagebox.showinfo(
                "Vincula Telegram primero",
                f"Conecta tu cuenta con @{pm.BOT_USERNAME} en unos segundos antes de empezar.",
            )
            self._open_telegram_dialog()
            return

        if not self.config_data.get("profiles"):
            messagebox.showinfo(
                "Elige tu personaje",
                "Agrega y calibra tu personaje con '+ Nuevo' antes de iniciar.",
            )
            self._open_new_character_dialog()
            return

        cdp_url = self.config_data.get("browser", {}).get("cdp_url", pm.DEFAULT_CDP_URL)
        if not pm.is_cdp_ready(cdp_url):
            if messagebox.askyesno(
                "Abre el juego primero",
                "El navegador del juego todavía no está abierto.\n\n¿Quieres abrir sfgame.net ahora?",
            ):
                self._open_chrome()
            return

        pm.sync_active_profile(self.config_data)
        pm.save_config(self.config_data)

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
            messagebox.showerror("No se pudo iniciar", str(exc))
            return

        self.btn_play.set_style(
            text="■  DETENER FARMEO",
            bg=CRIMSON,
            hover_bg=CRIMSON_HOVER,
            border=CRIMSON_BORDER,
            hover_border="#ff9c94",
        )
        self.pill_bot.configure(text="● En marcha", fg=EMERALD_SOFT, highlightbackground=EMERALD)

        char = self.config_data.get("character_name", "")
        srv = self.config_data.get("server_id", "")
        if self.autostart_var.get():
            self._push_event(f"🚀  Farmeo iniciado con {char} ({srv}).", "gold_bold")
        else:
            self._push_event(f"📱  Bot en espera — envía /start en @{pm.BOT_USERNAME} para comenzar.", "sky")

        threading.Thread(target=self._stream_process_output, args=(self.bot_proc,), daemon=True).start()

    def _stream_process_output(self, proc: subprocess.Popen) -> None:
        if proc.stdout:
            for line in proc.stdout:
                formatted = format_activity_line(line)
                if formatted:
                    self.event_queue.put(formatted)
        proc.wait()
        self.after(0, self._on_bot_exited)

    def _stop_bot(self) -> None:
        if not self._is_bot_running():
            return
        self._push_event("⏹  Deteniendo farmeo...", "warn")
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
            text="▶  INICIAR FARMEO",
            bg=EMERALD,
            hover_bg=EMERALD_HOVER,
            border=EMERALD_BORDER,
            hover_border="#9bf0be",
        )
        self.pill_bot.configure(text="● En pausa", fg=TEXT_MUTED, highlightbackground=BORDER_SUBTLE)
        self._push_event("💤  Bot detenido.", "muted")

    # ------------------------------------------------------------------
    # Status Polling & Stylized Activity Feed
    # ------------------------------------------------------------------
    def _poll_status(self) -> None:
        cdp_url = self.config_data.get("browser", {}).get("cdp_url", pm.DEFAULT_CDP_URL)

        def check_game():
            ready = pm.is_cdp_ready(cdp_url)
            has_tab = pm.has_sfgame_tab(cdp_url) if ready else False
            self.after(0, lambda: self._update_game_pill(ready, has_tab))

        threading.Thread(target=check_game, daemon=True).start()
        self._refresh_summary()
        self.after(3000, self._poll_status)

    def _update_game_pill(self, ready: bool, has_tab: bool) -> None:
        if ready and has_tab:
            self.pill_game.configure(text="● Juego listo", fg=EMERALD_SOFT, highlightbackground=EMERALD)
        elif ready:
            self.pill_game.configure(text="● Abre sfgame.net", fg=AMBER, highlightbackground=AMBER)
        else:
            self.pill_game.configure(text="● Juego cerrado", fg=TEXT_MUTED, highlightbackground=BORDER_SUBTLE)

    def _drain_events(self) -> None:
        while True:
            try:
                msg, tag = self.event_queue.get_nowait()
            except queue.Empty:
                break
            self._push_event(msg, tag)
        self.after(150, self._drain_events)

    def _push_event(self, msg: str, tag: str = "info") -> None:
        now = datetime.datetime.now().strftime("%H:%M")
        self.feed_text.configure(state="normal")
        self.feed_text.insert("end", f"{now}   ", "time")
        self.feed_text.insert("end", msg + "\n", tag)
        self.feed_text.see("end")
        self.feed_text.configure(state="disabled")

    def _clear_feed(self) -> None:
        self.feed_text.configure(state="normal")
        self.feed_text.delete("1.0", "end")
        self.feed_text.configure(state="disabled")

    def _on_close(self) -> None:
        if self._is_bot_running():
            self._stop_bot()
        self.destroy()


def main() -> None:
    app = ShakesFortuneApp()
    app.mainloop()


if __name__ == "__main__":
    main()
