#!/usr/bin/env python3
"""A simple, live controller for the Notion meeting-audio bridge."""

from __future__ import annotations

import math
import os
import re
import shutil
import struct
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cairo
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

APP_ID = "io.github.samuelrawrs.NotionRecorder"
APP_NAME = "Notion Recorder"
VERSION = "1.0.0"
WEBSITE = "https://github.com/samuelrawrs/notion-recorder"

ROOT = Path(__file__).resolve().parent
BRIDGE = ROOT / "notion-meeting-audio"
LOGO = ROOT / "data" / f"{APP_ID}.svg"
MIX_SINK = "notion_meeting_mix"
MIX_SOURCE = "notion_meeting_mix_source"

DEFAULT_MIC_LABEL = "System default microphone"
DEFAULT_OUTPUT_LABEL = "System default speaker output"

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.7, 1.8, 0.1

# Shown once on startup (and on demand) as a dialog before the first call.
FIRST_CALL_RULES = [
    ("In Notion", "pick \u201cNotion Meeting Mix\u201d as the microphone."),
    ("In Meet / Zoom / Teams", "keep your real microphone. Never pick the Mix, or people hear echo."),
    ("Headphones (recommended)", "keeps your speakers from feeding audio back into the mic. Not required."),
]

DAEMON_UNIT = "notion-recorder-daemon.service"

DEFAULT_THEME = "mint"
THEME_ORDER = ["mint", "snow", "dark", "ember"]
THEME_LABELS = {
    "mint": "Mint (default)",
    "snow": "Snow (light)",
    "dark": "Dark",
    "ember": "Ember (orange)",
}

# Each theme is a flat palette of colour tokens turned into GTK @define-color
# entries, plus two non-colour keys: "dark" (drives the libadwaita colour
# scheme so native popovers match) and "font" (optional family override).
THEMES: dict[str, dict[str, object]] = {
    "mint": {
        "dark": False,
        "font": None,
        "surface_top": "#f4f7f9", "surface_bottom": "#e8eef2",
        "ink": "#10201b", "ink_soft": "#64756e",
        "card": "#ffffff", "card_line": "#e5ece8",
        "panel_top": "#f0f6f2", "panel_bottom": "#e3efe9", "panel_line": "#e0ebe5",
        "brand": "#0aa06f", "brand_lit": "#13bd88", "on_brand": "#ffffff", "brand_ink": "#0b7a58",
        "sw_on": "#ffffff", "sw_on_ink": "#0b7a57",
        "busy_bg": "#e6ede9", "busy_ink": "#5c6d66",
        "repair_bg": "rgba(255,255,255,.65)", "repair_line": "#bfe0d1",
        "sink_bg": "#eef2ff", "sink_line": "#d7defb", "sink_ink": "#3b3ea8",
    },
    "snow": {
        "dark": False,
        "font": None,
        "surface_top": "#ffffff", "surface_bottom": "#eef1f4",
        "ink": "#111827", "ink_soft": "#6b7280",
        "card": "#ffffff", "card_line": "#e5e7eb",
        "panel_top": "#fbfcfd", "panel_bottom": "#f2f4f7", "panel_line": "#e5e7eb",
        "brand": "#2563eb", "brand_lit": "#3b82f6", "on_brand": "#ffffff", "brand_ink": "#2563eb",
        "sw_on": "#ffffff", "sw_on_ink": "#2563eb",
        "busy_bg": "#eef0f3", "busy_ink": "#6b7280",
        "repair_bg": "rgba(255,255,255,.7)", "repair_line": "#d1d5db",
        "sink_bg": "#eef2ff", "sink_line": "#dbe3ff", "sink_ink": "#3b3ea8",
    },
    "dark": {
        "dark": True,
        "font": None,
        "surface_top": "#1b1e24", "surface_bottom": "#111318",
        "ink": "#e7eaf0", "ink_soft": "#9aa3b2",
        "card": "#22262e", "card_line": "#333945",
        "panel_top": "#23272f", "panel_bottom": "#191c22", "panel_line": "#343a46",
        "brand": "#4f8cff", "brand_lit": "#6ba0ff", "on_brand": "#ffffff", "brand_ink": "#7aa8ff",
        "sw_on": "#262b34", "sw_on_ink": "#7aa8ff",
        "busy_bg": "#262b34", "busy_ink": "#9aa3b2",
        "repair_bg": "rgba(255,255,255,.05)", "repair_line": "#3a4150",
        "sink_bg": "#202634", "sink_line": "#33405c", "sink_ink": "#93b4ff",
    },
    "ember": {
        "dark": True,
        "font": '"URW Gothic", "Avant Garde", "Century Gothic", sans-serif',
        "surface_top": "#1c1613", "surface_bottom": "#0d0a08",
        "ink": "#f6efe8", "ink_soft": "#b6a495",
        "card": "#241d18", "card_line": "#3a2c20",
        "panel_top": "#251d16", "panel_bottom": "#191410", "panel_line": "#3c2d1f",
        "brand": "#ec5a1d", "brand_lit": "#f26e2c", "on_brand": "#1a0e05", "brand_ink": "#e78a4c",
        "sw_on": "#2e241b", "sw_on_ink": "#e78a4c",
        "busy_bg": "#2a221b", "busy_ink": "#b6a495",
        "repair_bg": "rgba(255,255,255,.05)", "repair_line": "#4a3826",
        "sink_bg": "#2a2118", "sink_line": "#4a3826", "sink_ink": "#e5a172",
    },
}

_CSS_BODY = """
  window { background: linear-gradient(to bottom, @surface_top, @surface_bottom); color: @ink; }
  headerbar { background: transparent; color: @ink; border: 0; box-shadow: none; }
  .brandmark { border-radius: 7px; margin-left: 4px; }
  stackswitcher button { min-height: 34px; border-radius: 10px; font-weight: 700; padding: 0 16px; color: @ink_soft; }
  stackswitcher button:checked { background: @sw_on; color: @sw_on_ink; box-shadow: 0 2px 6px rgba(16,40,33,.10); }

  .state-card { background: @card; border: 1px solid @card_line; border-radius: 16px; padding: 16px; box-shadow: 0 6px 16px rgba(17,42,34,.06); }
  .eyebrow { color: @brand_ink; font-size: 12px; font-weight: 800; letter-spacing: .12em; }
  .state-title { color: @ink; font-size: 21px; font-weight: 800; }
  .state-detail { color: @ink_soft; font-size: 14px; }

  .dial-card { background: linear-gradient(155deg, @panel_top, @panel_bottom); border: 1px solid @panel_line; border-radius: 16px; padding: 14px; box-shadow: inset 0 1px 0 rgba(255,255,255,.06); }
  .dial-value { color: @ink; font-size: 16px; font-weight: 800; }
  .dial-title { color: @ink_soft; font-size: 13px; font-weight: 700; letter-spacing: .02em; }

  .pill { min-height: 38px; border-radius: 11px; font-weight: 800; padding: 0 14px; }
  .pill:disabled { opacity: 1; }
  button.start { background: linear-gradient(135deg, @brand_lit, @brand); color: @on_brand; border: 0; box-shadow: 0 4px 12px alpha(@brand, .18); }
  button.start:hover { background: linear-gradient(135deg, @brand_lit, @brand_lit); }
  button.stop { background: linear-gradient(135deg, #ff7a7a, #ef4d4d); color: #ffffff; border: 0; box-shadow: 0 8px 18px rgba(226,74,74,.30); }
  button.stop:hover { background: linear-gradient(135deg, #ff8a8a, #f25a5a); }
  button.busy { background: @busy_bg; color: @busy_ink; border: 0; box-shadow: none; }
  button.repair { background: @repair_bg; color: @brand_ink; border: 1px solid @repair_line; box-shadow: none; }
  button.repair:hover { background: @card; }

  .footer { color: @ink_soft; font-size: 14px; }
  .important-card { background: #fff7e6; border: 1px solid #f0b429; border-left: 4px solid #f0b429; border-radius: 14px; padding: 12px; box-shadow: 0 6px 16px rgba(146,100,10,.08); }
  .important-title { color: #8a5a00; font-size: 14px; font-weight: 800; letter-spacing: .01em; }
  .important-icon { color: #b7791f; }
  .important-rule { color: #6b4a12; font-size: 12px; }
  .important-dismiss { min-height: 22px; min-width: 22px; padding: 0; color: #8a5a00; }
  .unavailable-note { color: #a15c00; font-size: 13px; }
  .config-card { background: @card; border: 1px solid @card_line; border-radius: 14px; padding: 14px; box-shadow: 0 6px 16px rgba(17,42,34,.06); }
  .field-label { color: @ink; font-size: 14px; font-weight: 700; }
  .field-hint { color: @ink_soft; font-size: 13px; }
  .applied { color: @brand_ink; font-size: 13px; font-weight: 700; }
  dropdown { border-radius: 10px; }

  .flow-wrap { background: linear-gradient(155deg, @panel_top, @panel_bottom); border: 1px solid @panel_line; border-radius: 14px; padding: 14px; }
  .flow-title { color: @ink; font-size: 15px; font-weight: 800; }
  .flow-card { background: @card; border: 1px solid @panel_line; border-radius: 11px; padding: 7px 11px; color: @ink; font-weight: 700; box-shadow: 0 3px 8px rgba(17,42,34,.06); }
  .flow-card.mix { background: linear-gradient(135deg, @brand_lit, @brand); color: @on_brand; border: 0; box-shadow: 0 3px 9px alpha(@brand, .16); }
  .flow-card.sink { background: @sink_bg; border: 1px solid @sink_line; color: @sink_ink; box-shadow: 0 3px 8px rgba(59,62,168,.10); }
  .flow-arrow { color: @ink_soft; font-size: 20px; font-weight: 800; }
  .flow-note { color: @brand_ink; font-size: 13px; font-weight: 600; }
"""


def build_css(theme: str, zoom: float = 1.0) -> bytes:
    palette = THEMES.get(theme, THEMES[DEFAULT_THEME])
    defs = "".join(
        f"@define-color {key} {value};\n"
        for key, value in palette.items()
        if key not in ("dark", "font")
    )
    font = palette.get("font")
    font_rule = f"window {{ font-family: {font}; }}\n" if font else ""
    body = _CSS_BODY
    if abs(zoom - 1.0) > 0.001:
        body = re.sub(
            r"font-size:\s*(\d+)px",
            lambda m: f"font-size: {max(1, round(int(m.group(1)) * zoom))}px",
            body,
        )
    return (defs + font_rule + body).encode()


def theme_is_dark(theme: str) -> bool:
    return bool(THEMES.get(theme, THEMES[DEFAULT_THEME]).get("dark"))


def _systemctl(*args: str) -> subprocess.CompletedProcess[str] | None:
    """Run ``systemctl --user``; return None if systemctl itself is unavailable."""
    try:
        return subprocess.run(["systemctl", "--user", *args], text=True, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        return None


def daemon_available() -> bool:
    """True only when the daemon unit is actually known to ``systemctl --user``."""
    result = _systemctl("list-unit-files", DAEMON_UNIT)
    if result is None or result.returncode:
        return False
    return DAEMON_UNIT in result.stdout


def daemon_enabled() -> bool:
    # "enabled" (and "enabled-runtime") -> on; anything else / error -> off.
    result = _systemctl("is-enabled", DAEMON_UNIT)
    if result is None:
        return False
    return result.stdout.strip().startswith("enabled")


TRAY_BIN = "notion-recorder-tray"
AUTOSTART_FILE = Path.home() / ".config" / "autostart" / "notion-recorder-tray.desktop"


def tray_binary() -> str | None:
    """Resolve the tray helper: repo checkout first, then PATH."""
    sibling = ROOT / TRAY_BIN
    if sibling.exists():
        return str(sibling)
    return shutil.which(TRAY_BIN)


def tray_typelib_present() -> bool:
    """True if an AppIndicator GIR typelib is installed (without importing GTK3)."""
    names = ("AyatanaAppIndicator3-0.1.typelib", "AppIndicator3-0.1.typelib")
    dirs: list[str] = []
    env = os.environ.get("GI_TYPELIB_PATH")
    if env:
        dirs += env.split(os.pathsep)
    dirs += [
        "/usr/lib/girepository-1.0",
        "/usr/lib64/girepository-1.0",
        f"/usr/lib/{os.uname().machine}-linux-gnu/girepository-1.0",
    ]
    return any(os.path.exists(os.path.join(d, n)) for d in dirs for n in names)


def tray_available() -> bool:
    return bool(tray_binary()) and tray_typelib_present()


def tray_enabled() -> bool:
    return AUTOSTART_FILE.exists()


def _autostart_contents(exec_path: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Notion Recorder Tray\n"
        "Comment=Tray control for the Notion Meeting Mix\n"
        f"Exec={exec_path}\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "NoDisplay=true\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def enable_tray() -> bool:
    """Write the autostart entry and launch the tray now. Returns success."""
    binary = tray_binary()
    if not binary:
        return False
    try:
        AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART_FILE.write_text(_autostart_contents(binary))
    except OSError:
        return False
    try:
        subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


def disable_tray() -> None:
    """Remove the autostart entry and stop any running tray."""
    try:
        AUTOSTART_FILE.unlink()
    except OSError:
        pass
    # Bracket the first letter so the pkill invocation never matches itself.
    subprocess.run(["pkill", "-f", "[n]otion-recorder-tray"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


SETTINGS_FILE = Path.home() / ".config" / "notion-recorder" / "settings.conf"


def read_setting(key: str) -> str:
    try:
        for line in SETTINGS_FILE.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line[len(key) + 1:].strip()
    except OSError:
        pass
    return ""


def write_setting(key: str, value: str) -> None:
    lines: list[str] = []
    try:
        lines = SETTINGS_FILE.read_text().splitlines()
    except OSError:
        pass
    out, found = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text("\n".join(out) + "\n")
    except OSError:
        pass


@dataclass
class Device:
    name: str
    description: str
    is_monitor: bool = False


@dataclass
class RouteSnapshot:
    active: bool = False
    microphone: str | None = None
    system_audio: str | None = None
    output_synced: bool = False
    notion_captures: int = 0
    error: str | None = None
    descriptions: dict[str, str] = field(default_factory=dict)


class AudioDial:
    """A circular level meter drawn with a stroked Cairo ring."""

    TRACK = (0.87, 0.91, 0.89)

    def __init__(self, title: str) -> None:
        self.fraction = 0.0
        self.armed = False
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
        self.canvas = Gtk.DrawingArea(content_width=104, content_height=104)
        self.canvas.set_draw_func(self.draw)
        self.value = Gtk.Label(label="-- dB", halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.value.add_css_class("dial-value")
        overlay = Gtk.Overlay()
        overlay.set_child(self.canvas)
        overlay.add_overlay(self.value)
        self.title = Gtk.Label(label=title)
        self.title.add_css_class("dial-title")
        self.box.append(overlay)
        self.box.append(self.title)

    def set_armed(self, armed: bool) -> None:
        if armed == self.armed:
            return
        self.armed = armed
        if not armed:
            self.fraction = 0.0
            self.value.set_label("Off")
        self.canvas.queue_draw()

    def set_level(self, decibels: float | None) -> None:
        if decibels is None:
            self.fraction = 0.0
            self.value.set_label("Waiting" if self.armed else "Off")
        else:
            self.fraction = max(0.0, min(1.0, (decibels + 60) / 60))
            self.value.set_label(f"{decibels:.0f} dB" if decibels > -59 else "Quiet")
        self.canvas.queue_draw()

    @staticmethod
    def color_for(fraction: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Return (base, highlight) colors for a two-stop gradient by level."""
        if fraction < 0.58:
            return (0.05, 0.68, 0.52), (0.36, 0.85, 0.68)
        if fraction < 0.82:
            return (0.95, 0.60, 0.09), (0.99, 0.77, 0.31)
        return (0.93, 0.31, 0.29), (0.99, 0.47, 0.44)

    def draw(self, _area: Gtk.DrawingArea, ctx, width: int, height: int, *_data) -> None:
        cx, cy = width / 2, height / 2
        line_width = max(9.0, min(width, height) * 0.12)
        radius = min(width, height) / 2 - line_width / 2 - 2
        ctx.set_line_width(line_width)
        ctx.set_line_cap(1)  # cairo.LINE_CAP_ROUND
        ctx.set_source_rgb(*self.TRACK)
        ctx.arc(cx, cy, radius, 0, math.tau)
        ctx.stroke()
        start = -math.pi / 2
        visible = self.fraction if self.fraction else (0.045 if self.armed else 0.0)
        if visible > 0:
            base, highlight = self.color_for(self.fraction)
            gradient = cairo.LinearGradient(0, 0, width, height)
            gradient.add_color_stop_rgb(0, *highlight)
            gradient.add_color_stop_rgb(1, *base)
            ctx.set_source(gradient)
            ctx.arc(cx, cy, radius, start, start + math.tau * visible)
            ctx.stroke()


class AudioMeter:
    """Reads live RMS levels from a device with parec and feeds a dial."""

    def __init__(self, app: "NotionRecorder", key: str) -> None:
        self.app, self.key = app, key
        self.device: str | None = None
        self.process: subprocess.Popen[bytes] | None = None

    def set_device(self, device: str | None) -> None:
        if device == self.device:
            return
        self.stop()
        self.device = device
        if not device:
            GLib.idle_add(self.app.set_dial, self.key, None)
            return
        try:
            self.process = subprocess.Popen(
                ["parec", "--latency-msec=50", "--raw", "--format=s16le", "--rate=48000",
                 "--channels=1", "--device", device, "--client-name=Notion Recorder Meter",
                 f"--stream-name={self.key} level meter"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
            )
        except OSError:
            GLib.idle_add(self.app.set_dial, self.key, None)
            return
        threading.Thread(target=self.read_levels, args=(self.process,), daemon=True).start()

    def read_levels(self, process: subprocess.Popen[bytes]) -> None:
        stdout = process.stdout
        if stdout is None:
            return
        try:
            while process.poll() is None:
                data = stdout.read(4800)  # ~50 ms at 48 kHz mono s16le
                if not data:
                    break
                usable = len(data) - len(data) % 2
                samples = struct.iter_unpack("<h", data[:usable])
                energy = [sample[0] * sample[0] for sample in samples]
                if not energy:
                    continue
                rms = math.sqrt(sum(energy) / len(energy)) / 32768
                decibels = 20 * math.log10(max(rms, 1e-6))
                if process is self.process:
                    GLib.idle_add(self.app.set_dial, self.key, decibels)
        except (OSError, ValueError):
            pass

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process, self.device = None, None


class NotionRecorder(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self.window: Adw.ApplicationWindow | None = None
        self.action_button: Gtk.Button | None = None
        self.action_content: Adw.ButtonContent | None = None
        self.repair_button: Gtk.Button | None = None
        self.status_label: Gtk.Label | None = None
        self.detail_label: Gtk.Label | None = None
        self.footer_label: Gtk.Label | None = None
        self.mic_dropdown: Gtk.DropDown | None = None
        self.output_dropdown: Gtk.DropDown | None = None
        self.mic_applied: Gtk.Label | None = None
        self.output_applied: Gtk.Label | None = None
        self.auto_switch: Gtk.Switch | None = None
        self.tray_switch: Gtk.Switch | None = None
        self.mic_devices: list[Device] = []
        self.output_devices: list[Device] = []
        self.dials: dict[str, AudioDial] = {}
        self.meters = {key: AudioMeter(self, key) for key in ("Microphone", "System audio")}
        self.snapshot = RouteSnapshot()
        self.action_in_flight = False
        self.refresh_source_id: int | None = None
        self.desc_cache: dict[str, str] = {}
        self.desc_cache_at: float = 0.0
        self.paused = False
        self.theme = read_setting("theme") or DEFAULT_THEME
        if self.theme not in THEMES:
            self.theme = DEFAULT_THEME
        self.css_provider: Gtk.CssProvider | None = None
        self.theme_dropdown: Gtk.DropDown | None = None
        try:
            self.zoom = float(read_setting("zoom") or "1.0")
        except ValueError:
            self.zoom = 1.0
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom))

    POLL_MS = 1500
    DESC_TTL = 5.0

    def do_activate(self) -> None:
        if self.window:
            self.window.present()
            return
        Gtk.Window.set_default_icon_name(APP_ID)
        self.load_css()
        self.setup_actions()
        self.window = Adw.ApplicationWindow(application=self, title=APP_NAME, default_width=470, default_height=600)
        self.window.set_icon_name(APP_ID)
        self.window.connect("close-request", self.on_close)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        brand = Gtk.Image.new_from_file(str(LOGO)) if LOGO.exists() else Gtk.Image.new_from_icon_name(APP_ID)
        brand.set_pixel_size(24)
        brand.add_css_class("brandmark")
        header.pack_start(brand)
        stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, vhomogeneous=False)
        switcher = Gtk.StackSwitcher(stack=stack)
        header.set_title_widget(switcher)
        menu = Gio.Menu()
        zoom_section = Gio.Menu()
        zoom_section.append("Zoom in", "app.zoom-in")
        zoom_section.append("Zoom out", "app.zoom-out")
        zoom_section.append("Reset zoom", "app.zoom-reset")
        menu.append_section(None, zoom_section)
        misc_section = Gio.Menu()
        misc_section.append("Show first-call tips", "app.tips")
        misc_section.append(f"About {APP_NAME}", "app.about")
        menu.append_section(None, misc_section)
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Main menu")
        header.pack_end(menu_button)
        toolbar.add_top_bar(header)
        recorder_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=14, margin_bottom=14, margin_start=18, margin_end=18)
        recorder_page.append(self.build_state_card())
        recorder_page.append(self.build_dials())
        recorder_page.append(self.build_footer())
        stack.add_titled(self.clamp(recorder_page), "recorder", "Recorder")
        stack.add_titled(self.clamp(self.build_config_page()), "config", "Configuration")
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scroller.set_child(stack)
        toolbar.set_content(scroller)
        self.window.set_content(toolbar)
        self.window.connect("notify::suspended", self.on_suspended)
        self.window.present()
        self.refresh()
        GLib.timeout_add(350, self.maybe_show_first_call)
        GLib.timeout_add(250, self.auto_start_if_needed)
        for delay in (150, 500, 1200):
            GLib.timeout_add(delay, self.refresh_once)
        self.refresh_source_id = GLib.timeout_add(self.POLL_MS, self.refresh)

    def on_suspended(self, window: Adw.ApplicationWindow, _param) -> None:
        """Pause meters and polling while the window is minimized or fully occluded."""
        suspended = bool(window.get_property("suspended"))
        if suspended and not self.paused:
            self.paused = True
            for meter in self.meters.values():
                meter.stop()
            if self.refresh_source_id:
                GLib.source_remove(self.refresh_source_id)
                self.refresh_source_id = None
        elif not suspended and self.paused:
            self.paused = False
            self.refresh()
            self.refresh_source_id = GLib.timeout_add(self.POLL_MS, self.refresh)

    def setup_actions(self) -> None:
        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", self.show_about)
        self.add_action(about)
        tips = Gio.SimpleAction.new("tips", None)
        tips.connect("activate", self.show_first_call)
        self.add_action(tips)
        zoom_actions = (
            ("zoom-in", lambda *_: self.change_zoom(ZOOM_STEP),
             ["<Primary>plus", "<Primary>equal", "<Primary>KP_Add"]),
            ("zoom-out", lambda *_: self.change_zoom(-ZOOM_STEP),
             ["<Primary>minus", "<Primary>KP_Subtract"]),
            ("zoom-reset", lambda *_: self.reset_zoom(), ["<Primary>0", "<Primary>KP_0"]),
        )
        for name, callback, accels in zoom_actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            self.set_accels_for_action(f"app.{name}", accels)

    def show_about(self, *_args) -> None:
        about = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=APP_ID,
            developer_name="samuelrawrs",
            version=VERSION,
            comments=(
                "Creates a private, capture-only microphone that mixes your voice with your "
                "meeting and system audio for Notion AI Meeting Notes. The mix is never played "
                "back to your speakers, so participants hear no echo.\n\n"
                "Any app that records from a microphone can select the Notion Meeting Mix input."
            ),
            website=WEBSITE,
            issue_url=f"{WEBSITE}/issues",
            license_type=Gtk.License.MIT_X11,
            copyright="\u00a9 2026 samuelrawrs",
            developers=["samuelrawrs"],
        )
        if LOGO.exists():
            about.set_application_icon(APP_ID)
        about.present(self.window)

    def load_css(self) -> None:
        self._apply_color_scheme()
        self._apply_dial_track()
        self._reload_css()

    def _reload_css(self) -> None:
        display = Gdk.Display.get_default()
        if self.css_provider is not None:
            Gtk.StyleContext.remove_provider_for_display(display, self.css_provider)
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(build_css(self.theme, self.zoom))
        Gtk.StyleContext.add_provider_for_display(
            display, self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        for dial in self.dials.values():
            dial.canvas.queue_draw()

    def _apply_color_scheme(self) -> None:
        scheme = Adw.ColorScheme.FORCE_DARK if theme_is_dark(self.theme) else Adw.ColorScheme.FORCE_LIGHT
        Adw.StyleManager.get_default().set_color_scheme(scheme)

    def _apply_dial_track(self) -> None:
        # Ring track colour: a soft charcoal on dark skins, neutral grey on light.
        AudioDial.TRACK = (0.24, 0.23, 0.22) if theme_is_dark(self.theme) else (0.88, 0.90, 0.92)

    def apply_theme(self, theme: str) -> None:
        self.theme = theme if theme in THEMES else DEFAULT_THEME
        write_setting("theme", self.theme)
        self._apply_color_scheme()
        self._apply_dial_track()
        self._reload_css()

    def on_theme_changed(self, dropdown: Gtk.DropDown, _param) -> None:
        index = dropdown.get_selected()
        if 0 <= index < len(THEME_ORDER):
            self.apply_theme(THEME_ORDER[index])

    def change_zoom(self, delta: float) -> None:
        new_zoom = round(max(ZOOM_MIN, min(ZOOM_MAX, self.zoom + delta)), 2)
        if abs(new_zoom - self.zoom) < 0.001:
            return
        self.zoom = new_zoom
        write_setting("zoom", str(self.zoom))
        self._reload_css()

    def reset_zoom(self) -> None:
        if abs(self.zoom - 1.0) < 0.001:
            return
        self.zoom = 1.0
        write_setting("zoom", "1.0")
        self._reload_css()

    @staticmethod
    def clamp(child: Gtk.Widget) -> Adw.Clamp:
        return Adw.Clamp(child=child, maximum_size=440, tightening_threshold=380)

    def build_state_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("state-card")
        eyebrow = Gtk.Label(label="MEETING AUDIO", xalign=0)
        eyebrow.add_css_class("eyebrow")
        self.status_label = Gtk.Label(label="Checking audio routes", xalign=0)
        self.status_label.add_css_class("state-title")
        self.detail_label = Gtk.Label(label="One click mixes your microphone and call audio for Notion.", xalign=0, wrap=True)
        self.detail_label.add_css_class("state-detail")
        self.action_button = Gtk.Button(hexpand=True)
        self.action_content = Adw.ButtonContent(label="Start bridge", icon_name="media-playback-start-symbolic", halign=Gtk.Align.CENTER)
        self.action_button.set_child(self.action_content)
        self.action_button.add_css_class("start")
        self.action_button.add_css_class("pill")
        self.action_button.connect("clicked", self.on_action)
        self.repair_button = Gtk.Button()
        self.repair_button.set_child(Adw.ButtonContent(label="Refresh routes", icon_name="view-refresh-symbolic", halign=Gtk.Align.CENTER))
        self.repair_button.add_css_class("repair")
        self.repair_button.add_css_class("pill")
        self.repair_button.connect("clicked", lambda _: self.refresh())
        card.append(eyebrow)
        card.append(self.status_label)
        card.append(self.detail_label)
        card.append(self.action_button)
        card.append(self.repair_button)
        return card

    def build_dials(self) -> Gtk.Widget:
        card = Gtk.Box(spacing=12, homogeneous=True, halign=Gtk.Align.CENTER)
        card.add_css_class("dial-card")
        for key in ("Microphone", "System audio"):
            dial = AudioDial(key)
            self.dials[key] = dial
            card.append(dial.box)
        return card

    def maybe_show_first_call(self) -> bool:
        """On startup, show the tips dialog unless the user hid it."""
        if read_setting("important_dismissed") != "1":
            self.show_first_call()
        return False

    def show_first_call(self, *_args) -> None:
        body = "\n".join(
            f"<b>{GLib.markup_escape_text(lead)}:</b> {GLib.markup_escape_text(rest)}"
            for lead, rest in FIRST_CALL_RULES
        )
        dialog = Adw.AlertDialog(heading="Read before your first call")
        dialog.set_body_use_markup(True)
        dialog.set_body(body)
        check = Gtk.CheckButton(label="Don\u2019t show this on startup")
        check.set_active(read_setting("important_dismissed") == "1")
        dialog.set_extra_child(check)
        dialog.add_response("close", "Got it")
        dialog.set_default_response("close")
        dialog.set_close_response("close")
        dialog.connect(
            "response",
            lambda _d, _r: write_setting("important_dismissed", "1" if check.get_active() else "0"),
        )
        dialog.present(self.window)

    def build_config_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=14, margin_bottom=14, margin_start=18, margin_end=18)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("config-card")
        title = Gtk.Label(label="Choose what Notion receives", xalign=0)
        title.add_css_class("state-title")
        note = Gtk.Label(label="Mixed into the private Notion input. Your call keeps using your own mic and headphones.", xalign=0, wrap=True)
        note.add_css_class("state-detail")
        card.append(title)
        card.append(note)

        self.mic_devices = self.list_devices("sources", monitors=False)
        self.output_devices = self.list_devices("sinks", monitors=False)
        self.mic_dropdown = Gtk.DropDown.new_from_strings([DEFAULT_MIC_LABEL, *(d.description for d in self.mic_devices)])
        self.output_dropdown = Gtk.DropDown.new_from_strings([DEFAULT_OUTPUT_LABEL, *(d.description for d in self.output_devices)])
        self.preselect(self.mic_dropdown, self.mic_devices, self.saved_value("source"))
        self.preselect(self.output_dropdown, self.output_devices, self.saved_value("sink"))

        card.append(self.labeled(
            "Your voice sent to Notion", "",
            self.mic_dropdown))
        self.mic_applied = Gtk.Label(label="", xalign=0, wrap=True)
        self.mic_applied.add_css_class("applied")
        card.append(self.mic_applied)

        card.append(self.labeled(
            "Meeting and system sound sent to Notion", "",
            self.output_dropdown))
        self.output_applied = Gtk.Label(label="", xalign=0, wrap=True)
        self.output_applied.add_css_class("applied")
        card.append(self.output_applied)

        save = Gtk.Button()
        save.set_child(Adw.ButtonContent(label="Save and restart bridge", icon_name="view-refresh-symbolic", halign=Gtk.Align.CENTER))
        save.add_css_class("start")
        save.add_css_class("pill")
        save.set_margin_top(6)
        save.connect("clicked", self.apply_config)
        card.append(save)

        page.append(self.build_automation_card())
        page.append(card)
        page.append(self.build_appearance_card())
        page.append(self.build_diagram())
        return page

    def build_appearance_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("config-card")
        title = Gtk.Label(label="Appearance", xalign=0)
        title.add_css_class("state-title")
        note = Gtk.Label(label="Pick a skin. It applies instantly and is remembered.", xalign=0, wrap=True)
        note.add_css_class("state-detail")
        card.append(title)
        card.append(note)
        self.theme_dropdown = Gtk.DropDown.new_from_strings([THEME_LABELS[k] for k in THEME_ORDER])
        self.theme_dropdown.set_selected(THEME_ORDER.index(self.theme) if self.theme in THEME_ORDER else 0)
        self.theme_dropdown.connect("notify::selected", self.on_theme_changed)
        card.append(self.labeled("Skin", "", self.theme_dropdown))
        return card

    @staticmethod
    def switch_row(title: str, hint: str, switch: Gtk.Switch) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        label = Gtk.Label(label=title, xalign=0)
        label.add_css_class("field-label")
        sub = Gtk.Label(label=hint, xalign=0, wrap=True)
        sub.add_css_class("field-hint")
        text.append(label)
        text.append(sub)
        row.append(text)
        row.append(switch)
        return row

    @staticmethod
    def unavailable_note(text: str) -> Gtk.Widget:
        note = Gtk.Label(label=text, xalign=0, wrap=True)
        note.add_css_class("unavailable-note")
        return note

    def build_auto_row(self) -> Gtk.Widget:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=14)
        self.auto_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        available = daemon_available()
        # Set the initial state before connecting so it never fires the handler.
        self.auto_switch.set_active(available and daemon_enabled())
        self.auto_switch.connect("notify::active", self.on_auto_toggle)
        container.append(self.switch_row(
            "Auto-start when I use the mic",
            "Starts the mix automatically during calls, via a background service.",
            self.auto_switch))
        if not available:
            self.auto_switch.set_sensitive(False)
            container.append(self.unavailable_note(
                "Available once Notion Recorder is installed from the package, which registers the background service."))
        return container

    def build_tray_row(self) -> Gtk.Widget:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=14)
        self.tray_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        available = tray_available()
        # Set initial state before connecting so it never fires the handler.
        self.tray_switch.set_active(available and tray_enabled())
        self.tray_switch.connect("notify::active", self.on_tray_toggle)
        container.append(self.switch_row(
            "Show a tray icon",
            "Adds a top-bar menu to start or stop the mix without opening this window.",
            self.tray_switch))
        if not available:
            self.tray_switch.set_sensitive(False)
            container.append(self.unavailable_note(
                "Install gir1.2-ayatanaappindicator3-0.1 (and, on GNOME, the AppIndicator extension) to enable the tray icon."))
        return container

    def build_automation_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("config-card")
        title = Gtk.Label(label="Automation", xalign=0)
        title.add_css_class("state-title")
        note = Gtk.Label(label="Optional conveniences. Both stay off until you switch them on.", xalign=0, wrap=True)
        note.add_css_class("state-detail")
        card.append(title)
        card.append(note)
        card.append(self.build_auto_row())
        card.append(self.build_tray_row())
        return card

    @staticmethod
    def labeled(label: str, hint: str, widget: Gtk.Widget) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=8)
        title = Gtk.Label(label=label, xalign=0)
        title.add_css_class("field-label")
        box.append(title)
        if hint:
            subtitle = Gtk.Label(label=hint, xalign=0, wrap=True)
            subtitle.add_css_class("field-hint")
            box.append(subtitle)
        box.append(widget)
        return box

    @staticmethod
    def preselect(dropdown: Gtk.DropDown, devices: list[Device], saved: str) -> None:
        if not saved:
            dropdown.set_selected(0)
            return
        for index, device in enumerate(devices):
            if device.name == saved:
                dropdown.set_selected(index + 1)
                return
        dropdown.set_selected(0)

    def build_diagram(self) -> Gtk.Widget:
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wrap.add_css_class("flow-wrap")
        heading = Gtk.Label(label="How the audio flows", halign=Gtk.Align.CENTER)
        heading.add_css_class("flow-title")
        wrap.append(heading)

        steps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
        inputs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.CENTER)
        inputs.append(self.flow_card("Your microphone"))
        inputs.append(self.flow_card("Meeting audio"))
        steps.append(inputs)
        steps.append(self.flow_arrow("\u2193"))
        steps.append(self.flow_card("Private Notion Mix", "mix"))
        steps.append(self.flow_arrow("\u2193"))
        steps.append(self.flow_card("Notion transcript", "sink"))
        wrap.append(steps)

        note = Gtk.Label(
            label="Capture-only: the mix reaches Notion but never your headphones, so no echo. Your call keeps using your real mic.",
            xalign=0, wrap=True)
        note.add_css_class("flow-note")
        wrap.append(note)
        return wrap

    @staticmethod
    def flow_card(text: str, variant: str | None = None) -> Gtk.Widget:
        label = Gtk.Label(label=text, halign=Gtk.Align.CENTER)
        label.add_css_class("flow-card")
        if variant:
            label.add_css_class(variant)
        return label

    @staticmethod
    def flow_arrow(text: str) -> Gtk.Widget:
        arrow = Gtk.Label(label=text, valign=Gtk.Align.CENTER)
        arrow.add_css_class("flow-arrow")
        return arrow

    def list_devices(self, kind: str, monitors: bool) -> list[Device]:
        try:
            output = self.pactl("list", kind)
        except RuntimeError:
            return []
        devices: list[Device] = []
        name = desc = None
        is_monitor = False

        def flush() -> None:
            nonlocal name, desc, is_monitor
            if name and name not in (MIX_SINK, MIX_SOURCE):
                if monitors or not is_monitor:
                    devices.append(Device(name, desc or name, is_monitor))
            name = desc = None
            is_monitor = False

        for line in output.splitlines():
            if line and not line[0].isspace():
                flush()
                continue
            stripped = line.strip()
            if stripped.startswith("Name:"):
                name = stripped[5:].strip()
            elif stripped.startswith("Description:"):
                desc = stripped[12:].strip()
            elif stripped.startswith("Monitor of Sink:"):
                is_monitor = stripped.split(":", 1)[1].strip() != "n/a"
        flush()
        return devices

    def describe(self, name: str | None) -> str:
        if not name:
            return "system default"
        return self.snapshot.descriptions.get(name, name)

    def apply_config(self, _: Gtk.Button) -> None:
        source = self.selected_name(self.mic_dropdown, self.mic_devices)
        sink = self.selected_name(self.output_dropdown, self.output_devices)
        threading.Thread(target=self.run_config, args=(source, sink), daemon=True).start()

    @staticmethod
    def selected_name(dropdown: Gtk.DropDown, devices: list[Device]) -> str:
        index = dropdown.get_selected()
        return devices[index - 1].name if index else ""

    def run_config(self, source: str, sink: str) -> None:
        saved = subprocess.run([str(BRIDGE), "configure", source, sink], text=True, capture_output=True)
        restarted = subprocess.run([str(BRIDGE), "restart"], text=True, capture_output=True) if not saved.returncode else saved
        GLib.idle_add(self.finish_config, saved, restarted)

    def finish_config(self, saved: subprocess.CompletedProcess[str], restarted: subprocess.CompletedProcess[str]) -> bool:
        self.refresh()
        if saved.returncode or restarted.returncode:
            self.detail_label.set_label((saved.stderr or restarted.stderr).strip() or "Could not apply the selected devices.")
        return False

    def on_auto_toggle(self, switch: Gtk.Switch, _param) -> None:
        want = switch.get_active()
        threading.Thread(target=self._run_auto_toggle, args=(want,), daemon=True).start()

    def _run_auto_toggle(self, want: bool) -> None:
        verb = "enable" if want else "disable"
        result = _systemctl(verb, "--now", DAEMON_UNIT)
        GLib.idle_add(self._finish_auto_toggle, want, result)

    def _finish_auto_toggle(self, want: bool, result: subprocess.CompletedProcess[str] | None) -> bool:
        if result is None or result.returncode:
            # Revert without re-triggering the handler.
            self.auto_switch.handler_block_by_func(self.on_auto_toggle)
            self.auto_switch.set_active(not want)
            self.auto_switch.handler_unblock_by_func(self.on_auto_toggle)
            message = "" if result is None else result.stderr.strip()
            self.detail_label.set_label(message or "Could not change auto-start.")
        return False

    def on_tray_toggle(self, switch: Gtk.Switch, _param) -> None:
        want = switch.get_active()
        if want:
            if not enable_tray():
                # Revert without re-triggering the handler.
                switch.handler_block_by_func(self.on_tray_toggle)
                switch.set_active(False)
                switch.handler_unblock_by_func(self.on_tray_toggle)
                if self.detail_label is not None:
                    self.detail_label.set_label("Could not start the tray icon.")
        else:
            disable_tray()

    def build_footer(self) -> Gtk.Widget:
        self.footer_label = Gtk.Label(label="Notion: checking for a transcript using the virtual input", xalign=0, wrap=True)
        self.footer_label.add_css_class("footer")
        return self.footer_label

    @staticmethod
    def saved_value(key: str) -> str:
        path = Path.home() / ".config" / "notion-recorder" / "audio.conf"
        try:
            for line in path.read_text().splitlines():
                if line.startswith(f"{key}="):
                    return line[len(key) + 1:].strip()
        except OSError:
            pass
        return ""

    @staticmethod
    def pactl(*args: str) -> str:
        result = subprocess.run(["pactl", *args], text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Audio server unavailable")
        return result.stdout.strip()

    def device_descriptions(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for kind in ("sources", "sinks"):
            for device in self.list_devices(kind, monitors=True):
                mapping[device.name] = device.description
        return mapping

    def cached_descriptions(self) -> dict[str, str]:
        """Friendly names change rarely; refresh at most every DESC_TTL seconds."""
        now = time.monotonic()
        if not self.desc_cache or now - self.desc_cache_at > self.DESC_TTL:
            self.desc_cache = self.device_descriptions()
            self.desc_cache_at = now
        return self.desc_cache

    def inspect_routes(self) -> RouteSnapshot:
        try:
            sources = self.pactl("list", "short", "sources").splitlines()
            sinks = self.pactl("list", "short", "sinks").splitlines()
            modules = self.pactl("list", "short", "modules").splitlines()
            outputs = self.pactl("list", "short", "source-outputs").splitlines()
            default_sink = self.pactl("get-default-sink")
            descriptions = self.cached_descriptions()
        except RuntimeError as error:
            return RouteSnapshot(error=str(error))
        source_ids = {parts[1]: parts[0] for line in sources if len(parts := line.split()) > 1}
        active = MIX_SOURCE in source_ids and any(len(parts := line.split()) > 1 and parts[1] == MIX_SINK for line in sinks)
        loops = [line for line in modules if "module-loopback" in line and f"sink={MIX_SINK}" in line]
        microphone = next((token[7:] for line in loops for token in line.split() if token.startswith("source=") and not token.endswith(".monitor")), None)
        system = next((token[7:] for line in loops for token in line.split() if token.startswith("source=") and token.endswith(".monitor")), None)
        capture_id = source_ids.get(MIX_SOURCE)
        captures = sum(1 for line in outputs if len(parts := line.split()) > 1 and parts[1] == capture_id)
        return RouteSnapshot(active, microphone, system, system == f"{default_sink}.monitor", captures, descriptions=descriptions)

    def auto_start_if_needed(self) -> bool:
        if not self.snapshot.active and not self.action_in_flight and not self.snapshot.error:
            self.on_action(None)
        return False

    def refresh_once(self) -> bool:
        self.refresh()
        return False

    def refresh(self) -> bool:
        self.snapshot = self.inspect_routes()
        if not self.action_in_flight:
            self.render_state()
        self.update_applied()
        self.dials["Microphone"].set_armed(bool(self.snapshot.active and self.snapshot.microphone))
        self.dials["System audio"].set_armed(bool(self.snapshot.active and self.snapshot.system_audio))
        self.meters["Microphone"].set_device(self.snapshot.microphone if self.snapshot.active else None)
        self.meters["System audio"].set_device(self.snapshot.system_audio if self.snapshot.active else None)
        return True

    def update_applied(self) -> None:
        if self.mic_applied is None or self.output_applied is None:
            return
        if self.snapshot.active and self.snapshot.microphone:
            self.mic_applied.set_label(f"Now sending: {self.describe(self.snapshot.microphone)}")
        else:
            self.mic_applied.set_label("Not active yet.")
        if self.snapshot.active and self.snapshot.system_audio:
            sink = self.snapshot.system_audio[:-len(".monitor")] if self.snapshot.system_audio.endswith(".monitor") else self.snapshot.system_audio
            suffix = "" if self.snapshot.output_synced else " (differs from current default output)"
            self.output_applied.set_label(f"Now sending: {self.describe(sink)}{suffix}")
        else:
            self.output_applied.set_label("Not active yet.")

    def set_action(self, label: str, icon: str) -> None:
        self.action_content.set_label(label)
        self.action_content.set_icon_name(icon)

    def render_state(self) -> None:
        snap = self.snapshot
        for css in ("start", "stop", "busy"):
            self.action_button.remove_css_class(css)
        self.action_button.set_sensitive(True)
        if snap.error:
            self.status_label.set_label("Audio server unavailable")
            self.detail_label.set_label(snap.error)
            self.set_action("Retry", "view-refresh-symbolic")
            self.action_button.add_css_class("start")
            self.footer_label.set_label("Notion: unavailable until PipeWire returns")
        elif snap.active:
            self.status_label.set_label("Bridge is on")
            self.detail_label.set_label("Mixed for Notion only. Your default mic is unchanged, so Google Meet is unaffected." if snap.output_synced else "Your speaker output changed. Refresh routes, then restart the bridge if needed.")
            self.set_action("Stop bridge", "media-playback-stop-symbolic")
            self.action_button.add_css_class("stop")
            self.footer_label.set_label("Notion: connected" if snap.notion_captures else "Notion: start a fresh transcript and choose \u201cNotion Meeting Mix\u201d")
        else:
            self.status_label.set_label("Bridge is off")
            self.detail_label.set_label("Start it immediately before a Notion transcript.")
            self.set_action("Start bridge", "media-playback-start-symbolic")
            self.action_button.add_css_class("start")
            self.footer_label.set_label("Notion: the virtual microphone is not active")

    def on_action(self, _: Gtk.Button | None) -> None:
        if self.action_in_flight:
            return
        self.action_in_flight = True
        stopping = self.snapshot.active
        self.set_action("Stopping\u2026" if stopping else "Starting\u2026", "process-working-symbolic")
        for css in ("start", "stop"):
            self.action_button.remove_css_class(css)
        self.action_button.add_css_class("busy")
        self.action_button.set_sensitive(False)
        self.repair_button.set_sensitive(False)
        self.status_label.set_label("Stopping bridge" if stopping else "Starting bridge")
        self.detail_label.set_label("Updating PipeWire routes\u2026")
        threading.Thread(target=self.run_action, args=("stop" if stopping else "start",), daemon=True).start()

    def run_action(self, command: str) -> None:
        result = subprocess.run([str(BRIDGE), command], text=True, capture_output=True)
        GLib.idle_add(self.finish_action, command, result)

    def finish_action(self, command: str, result: subprocess.CompletedProcess[str]) -> bool:
        self.action_in_flight = False
        self.snapshot = self.inspect_routes()
        self.render_state()
        self.update_applied()
        self.repair_button.set_sensitive(True)
        if result.returncode:
            self.detail_label.set_label(result.stderr.strip() or "The bridge command failed. Try again.")
        elif command == "stop" and self.snapshot.active:
            self.status_label.set_label("Bridge is still on")
            self.detail_label.set_label("Stop did not release every route. Click Stop again.")
        return False

    def set_dial(self, key: str, decibels: float | None) -> bool:
        self.dials[key].set_level(decibels)
        return False

    def on_close(self, _: Adw.ApplicationWindow) -> bool:
        for meter in self.meters.values():
            meter.stop()
        if self.refresh_source_id:
            GLib.source_remove(self.refresh_source_id)
        return False


if __name__ == "__main__":
    NotionRecorder().run()
