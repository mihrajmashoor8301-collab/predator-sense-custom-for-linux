#!/usr/bin/env python3
"""PredSenseLinux desktop control center for Linuwu-Sense."""
import json
import math
import pathlib
import shutil
import shlex
import socket
import subprocess
import time
import colorsys
import tkinter as tk
from tkinter import messagebox, ttk

BASE = pathlib.Path("/sys/devices/platform/acer-wmi")
PREDATOR = BASE / "predator_sense"
NITRO = BASE / "nitro_sense"
PROFILE = BASE / "platform-profile/platform-profile-0"
PROFILE_SOCKET = "/run/linuwu-profile-helper/profile.sock"
HWMON = pathlib.Path("/sys/class/hwmon")
NVIDIA_SMI = shutil.which("nvidia-smi")
BG = "#0b0d12"
PANEL = "#111720"
PANEL2 = "#19212c"
TEXT = "#f1f3f7"
MUTED = "#8992a3"
RED = "#f04452"
CYAN = "#50d9e8"
GREEN = "#59d99a"
ACCENT = "#16c9d2"


class GradientButton(tk.Canvas):
    """Compact raised button with a simple horizontal color gradient."""
    def __init__(self, parent, text, command, colors, width=104, height=36):
        super().__init__(parent, width=width, height=height, bg=PANEL, highlightthickness=0, cursor="hand2")
        self.label = text
        self.command = command
        self.colors = colors
        self.active = False
        self.bind("<Button-1>", lambda _event: self.command())
        self.bind("<Enter>", lambda _event: self._draw(hover=True))
        self.bind("<Leave>", lambda _event: self._draw())
        self._draw()

    @staticmethod
    def _mix(first, second, amount):
        a = tuple(int(first[index:index + 2], 16) for index in (1, 3, 5))
        b = tuple(int(second[index:index + 2], 16) for index in (1, 3, 5))
        return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * amount):02x}" for i in range(3))

    def set_active(self, active):
        self.active = active
        self._draw()

    def _draw(self, hover=False):
        self.delete("all")
        width, height = int(self.cget("width")), int(self.cget("height"))
        self.create_rectangle(2, 4, width - 2, height - 1, fill="#05080d", outline="")
        first, second = self.colors if self.active else ("#263140", "#18212c")
        if hover and not self.active:
            first, second = "#344558", "#202d3b"
        strips = max(2, width - 8)
        for x in range(strips):
            color = self._mix(first, second, x / (strips - 1))
            self.create_line(4 + x, 5, 4 + x, height - 4, fill=color, width=1)
        rim = self.colors[0] if self.active else "#354252"
        self.create_rectangle(3, 3, width - 3, height - 4, outline=rim, width=1)
        self.create_line(7, 5, width - 7, 5, fill="#bdfaff" if self.active else "#536174", width=1)
        self.create_text(width / 2, height / 2 + 1, text=self.label, fill="#071216" if self.active else TEXT,
                         font=("TkDefaultFont", 8, "bold"))


def read(path, default=""):
    try:
        return pathlib.Path(path).read_text().strip()
    except (OSError, ValueError):
        return default


def hwmon_read(chip, attribute, default="N/A"):
    try:
        for device in HWMON.glob("hwmon*"):
            if read(device / "name") == chip:
                return read(device / attribute, default)
    except OSError:
        pass
    return default


def cpu_temperature():
    try:
        for device in HWMON.glob("hwmon*"):
            if read(device / "name") != "coretemp":
                continue
            for label in device.glob("temp*_label"):
                if read(label).lower() == "package id 0":
                    return f"{int(read(label.with_name(label.name.replace('_label', '_input')))) / 1000:.0f}°"
    except (OSError, ValueError):
        pass
    return "--"


_gpu_temp = "--"
_gpu_updated = 0.0


def gpu_temperature():
    global _gpu_temp, _gpu_updated
    now = time.monotonic()
    if now - _gpu_updated > 3:
        _gpu_updated = now
        if NVIDIA_SMI:
            try:
                result = subprocess.run([NVIDIA_SMI, "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=2, check=True)
                _gpu_temp = f"{int(result.stdout.strip().splitlines()[0])}°"
            except (OSError, subprocess.SubprocessError, ValueError, IndexError):
                _gpu_temp = "--"
    return _gpu_temp


_cpu_counters = None


def cpu_usage():
    global _cpu_counters
    try:
        fields = pathlib.Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        counters = [int(value) for value in fields]
        total = sum(counters)
        idle = counters[3] + (counters[4] if len(counters) > 4 else 0)
        previous = _cpu_counters
        _cpu_counters = (total, idle)
        if previous is None:
            return "--%"
        total_delta, idle_delta = total - previous[0], idle - previous[1]
        return f"{max(0, min(100, round((total_delta - idle_delta) / total_delta * 100)))}%" if total_delta else "0%"
    except (OSError, IndexError, ValueError, ZeroDivisionError):
        return "--%"


_gpu_load = "--%"
_gpu_load_updated = 0.0


def gpu_usage():
    global _gpu_load, _gpu_load_updated
    now = time.monotonic()
    if now - _gpu_load_updated < 2:
        return _gpu_load
    _gpu_load_updated = now
    if NVIDIA_SMI:
        try:
            result = subprocess.run([NVIDIA_SMI, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=2, check=True)
            _gpu_load = f"{max(0, min(100, int(result.stdout.strip().splitlines()[0])))}%"
            return _gpu_load
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            pass
    try:
        for attribute in pathlib.Path("/sys/class/drm").glob("card*/device/gpu_busy_percent"):
            value = int(read(attribute, "--"))
            _gpu_load = f"{max(0, min(100, value))}%"
            return _gpu_load
    except (OSError, ValueError):
        pass
    _gpu_load = "--%"
    return _gpu_load


def write(path, value, label="Setting"):
    try:
        pathlib.Path(path).write_text(str(value))
        return True
    except OSError as exc:
        messagebox.showerror("PredSenseLinux", f"Couldn't update {label}.\n\n{exc}\n\nCheck that your account has access to the Linuwu-Sense controls.")
        return False


def discover_sense():
    if PREDATOR.is_dir():
        return PREDATOR, "PREDATOR"
    if NITRO.is_dir():
        return NITRO, "NITRO"
    return PREDATOR, "DEVICE NOT DETECTED"


SENSE, MODEL = discover_sense()


class SenseApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PredSenseLinux | Control Center")
        self.geometry("1360x860")
        self.minsize(1120, 740)
        self.configure(bg=BG)
        self.option_add("*Font", "TkDefaultFont 10")
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=BG)
        self.style.configure("Panel.TFrame", background=PANEL)
        self.style.configure("TLabel", background=BG, foreground=TEXT)
        self.style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        self.style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        self.style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("TkDefaultFont", 24, "bold"))
        self.style.configure("Hero.TLabel", background=PANEL, foreground=TEXT, font=("TkDefaultFont", 30, "bold"))
        self.style.configure("Accent.TButton", background=ACCENT, foreground="#071216", padding=(16, 10), borderwidth=2, relief="raised", lightcolor="#b7ffff", darkcolor="#087985", bordercolor="#2df1f3", font=("TkDefaultFont", 10, "bold"))
        self.style.map("Accent.TButton", background=[("active", "#60e5e9")])
        self.style.configure("Nav.TButton", background="#10151d", foreground="#aab3c1", padding=(15, 13), borderwidth=0, anchor="w", font=("TkDefaultFont", 10, "bold"))
        self.style.map("Nav.TButton", background=[("active", "#1c2932")], foreground=[("active", TEXT)])
        self.style.configure("NavActive.TButton", background="#102a30", foreground="#65e8ec", padding=(15, 13), borderwidth=0, anchor="w", font=("TkDefaultFont", 10, "bold"))
        self.style.configure("TButton", background=PANEL2, foreground=TEXT, padding=(11, 8), borderwidth=2, relief="raised", lightcolor="#455365", darkcolor="#121923", bordercolor="#2b3645")
        self.style.map("TButton", background=[("active", "#303746")])
        self.style.configure("Horizontal.TScale", background=PANEL, troughcolor="#303746")
        self.style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        self.style.map("TCheckbutton", background=[("active", PANEL)])
        self.style.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2, foreground=TEXT, arrowcolor=TEXT)
        self.style.map("TCombobox", fieldbackground=[("readonly", PANEL2), ("disabled", PANEL2)], foreground=[("readonly", TEXT), ("disabled", MUTED)], selectbackground=[("readonly", PANEL2)], selectforeground=[("readonly", TEXT)])
        self.style.configure("TSpinbox", fieldbackground=PANEL2, background=PANEL2, foreground=TEXT, arrowcolor=TEXT)
        self.option_add("*TCombobox*Listbox.background", PANEL2)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#071216")
        self.pages = {}
        self.profile_prefs = self._load_profile_preferences()
        self._power_source = None
        self._last_applied_profile = None
        self._build_shell()
        self.show_page("Overview")
        self.refresh()

    def _build_shell(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=30, pady=(22, 16))
        logo_tile = tk.Canvas(header, width=54, height=54, bg=BG, highlightthickness=0)
        logo_tile.pack(side="left", padx=(0, 14))
        # Original PredSenseLinux mark: a geometric system core with a custom PS monogram.
        logo_tile.create_polygon(27, 2, 50, 15, 50, 39, 27, 52, 4, 39, 4, 15,
                                 fill="#171c26", outline="#343c4d", width=2)
        logo_tile.create_text(27, 25, text="PS", fill=ACCENT, font=("TkDefaultFont", 16, "bold"))
        logo_tile.create_line(17, 37, 37, 37, fill=CYAN, width=2)
        logo_tile.create_oval(24, 41, 30, 47, fill=RED, outline="")
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left", anchor="center")
        tk.Label(brand, text="PredSenseLinux", bg=BG, fg=TEXT, font=("TkDefaultFont", 19, "bold")).pack(anchor="w")
        tk.Label(brand, text="PREDATOR SYSTEM CONTROL", bg=BG, fg="#758295", font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(2, 0))
        self.device_badge = tk.Label(header, text=f"●  {MODEL}", bg="#172620", fg=GREEN, padx=13, pady=8, font=("TkDefaultFont", 9, "bold"))
        self.device_badge.pack(side="right")
        hero = tk.Frame(self, bg=BG)
        hero.pack(fill="x", padx=30, pady=(0, 13))
        tk.Label(hero, text="Your system. Tuned.", bg=BG, fg=TEXT, font=("TkDefaultFont", 21, "bold")).pack(anchor="w")
        tk.Label(hero, text="Live performance, cooling and lighting controls.", bg=BG, fg=MUTED, font=("TkDefaultFont", 9)).pack(anchor="w", pady=(2, 0))
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=30, pady=(0, 24))
        nav = tk.Frame(body, bg="#0e131a", width=190, padx=9, pady=14, highlightthickness=1, highlightbackground="#202632")
        nav.pack(side="left", fill="y", padx=(0, 18))
        nav.pack_propagate(False)
        tk.Label(nav, text="CONTROL PANEL", bg="#10141b", fg="#697385", font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=5, pady=(3, 10))
        self.nav_buttons = {}
        for item, glyph in (("Overview", "◈"), ("Profiles", "◌"), ("Cooling", "◉"), ("Lighting", "✦"), ("Power", "ϟ")):
            button = ttk.Button(nav, text=f"{glyph}    {item}", style="Nav.TButton", command=lambda i=item: self.show_page(i))
            button.pack(fill="x", pady=3)
            self.nav_buttons[item] = button
        tk.Frame(nav, bg="#252c38", height=1).pack(fill="x", pady=13)
        tk.Label(nav, text="HARDWARE", bg="#10141b", fg="#697385", font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=5)
        tk.Label(nav, text=MODEL.title(), bg="#10141b", fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=5, pady=(7, 0))
        tk.Label(nav, text="Linuwu-Sense module", bg="#10141b", fg=MUTED, font=("TkDefaultFont", 9)).pack(anchor="w", padx=5, pady=(2, 0))
        self.page_area = tk.Frame(body, bg=BG)
        self.page_area.pack(side="left", fill="both", expand=True)
        for page, builder in (("Overview", self._overview), ("Profiles", self._profiles), ("Cooling", self._cooling), ("Lighting", self._lighting), ("Power", self._power)):
            frame = tk.Frame(self.page_area, bg=BG)
            self.pages[page] = frame
            builder(frame)

    def show_page(self, page):
        for frame in self.pages.values():
            frame.pack_forget()
        self.pages[page].pack(fill="both", expand=True)
        for name, button in self.nav_buttons.items():
            button.configure(style="NavActive.TButton" if name == page else "Nav.TButton")

    def card(self, parent, title, subtitle=None):
        box = tk.Frame(parent, bg=PANEL, padx=20, pady=18, highlightthickness=1, highlightbackground="#252c38")
        heading = tk.Frame(box, bg=PANEL)
        heading.pack(fill="x", anchor="w")
        tk.Frame(heading, bg=ACCENT, width=3, height=15).pack(side="left", padx=(0, 9))
        tk.Label(heading, text=title, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(side="left")
        if subtitle:
            tk.Label(box, text=subtitle, bg=PANEL, fg=MUTED, wraplength=680, justify="left").pack(anchor="w", pady=(4, 12))
        return box

    @staticmethod
    def _load_profile_preferences():
        defaults = {"ac": "balanced", "battery": "balanced"}
        try:
            stored = json.loads((pathlib.Path.home() / ".config/predsenselinux/profiles.json").read_text())
            for source in defaults:
                candidate = stored.get(source)
                valid = {"ac": {"quiet", "balanced", "balanced-performance", "performance"}, "battery": {"low-power", "balanced"}}
                if isinstance(candidate, str) and candidate in valid[source]:
                    defaults[source] = candidate
        except (OSError, ValueError, AttributeError):
            pass
        return defaults

    def _save_profile_preferences(self):
        path = pathlib.Path.home() / ".config/predsenselinux/profiles.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.profile_prefs, indent=2) + "\n")
        except OSError as exc:
            messagebox.showerror("PredSenseLinux", f"Could not save AC and battery profile choices.\n\n{exc}")

    @staticmethod
    def _power_source_online():
        try:
            for supply in pathlib.Path("/sys/class/power_supply").glob("*"):
                if read(supply / "type").lower() == "mains":
                    state = read(supply / "online")
                    if state in ("0", "1"):
                        return state == "1"
        except OSError:
            pass
        return None

    def _profiles(self, page):
        ttk.Label(page, text="Profiles", style="Title.TLabel").pack(anchor="w", pady=(0, 3))
        tk.Label(page, text="Choose separate thermal profiles for AC power and battery.", bg=BG, fg=MUTED, font=("TkDefaultFont", 9)).pack(anchor="w", pady=(0, 13))
        self.profile_source_state = tk.StringVar(value="Detecting power source…")
        source_card = self.card(page, "POWER SOURCE", "Your saved profile for the active power source is applied automatically while PredSenseLinux is running.")
        tk.Label(source_card, textvariable=self.profile_source_state, bg=PANEL, fg=CYAN, font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        source_card.pack(fill="x", pady=(0, 12))

        self.profile_choice_buttons = {"ac": {}, "battery": {}}
        self.profile_choice_vars = {source: tk.StringVar(value=self.profile_prefs[source]) for source in ("ac", "battery")}
        ac = self.card(page, "AC POWER", "Quiet Mode · Balanced · Performance · Turbo")
        self._profile_choices(ac, "ac", (("quiet", "QUIET MODE"), ("balanced", "BALANCED"), ("balanced-performance", "PERFORMANCE"), ("performance", "TURBO")))
        ac.pack(fill="x", pady=(0, 12))
        battery = self.card(page, "BATTERY POWER", "Power Saver · Balanced")
        self._profile_choices(battery, "battery", (("low-power", "POWER SAVER"), ("balanced", "BALANCED")))
        battery.pack(fill="x")
        self.profile_notice = tk.StringVar(value="")
        tk.Label(page, textvariable=self.profile_notice, bg=BG, fg=MUTED, justify="left", wraplength=760).pack(anchor="w", pady=12)

    def _profile_choices(self, parent, source, choices):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x")
        for index, (value, label) in enumerate(choices):
            button = ttk.Button(row, text=label, command=lambda s=source, v=value: self.choose_profile(s, v))
            button.grid(row=index // 4, column=index % 4, sticky="ew", padx=(0, 7), pady=4)
            row.grid_columnconfigure(index % 4, weight=1, uniform=f"{source}-profile")
            self.profile_choice_buttons[source][value] = button

    def choose_profile(self, source, value):
        allowed = {"ac": {"quiet", "balanced", "balanced-performance", "performance"}, "battery": {"low-power", "balanced"}}
        if source not in allowed or value not in allowed[source]:
            return
        self.profile_prefs[source] = value
        self.profile_choice_vars[source].set(value)
        self._save_profile_preferences()
        self._render_profile_choices()
        online = self._power_source_online()
        active = "ac" if online is True else "battery" if online is False else None
        if active == source:
            self.set_profile(value)
        else:
            self.profile_notice.set(f"{value.replace('-', ' ').title()} saved for {source} power; it will apply when that source is active.")

    def _render_profile_choices(self):
        if not hasattr(self, "profile_choice_buttons"):
            return
        choices = set(self.profile_choices)
        active_source = "ac" if self._power_source is True else "battery" if self._power_source is False else None
        for source, buttons in self.profile_choice_buttons.items():
            for value, button in buttons.items():
                available = value in choices
                button.configure(state="normal" if available else "disabled",
                                 style="Accent.TButton" if value == self.profile_prefs[source] else "TButton")
        if hasattr(self, "active_profile"):
            self.active_profile.set(read(PROFILE / "profile", "unknown").replace("-", " ").title())
        if active_source:
            current = read(PROFILE / "profile", "unknown").replace("-", " ").title()
            saved = self.profile_prefs[active_source].replace("-", " ").title()
            state = "AC power connected" if active_source == "ac" else "Running on battery"
            self.profile_source_state.set(f"{state}  ·  Active: {current}  ·  Saved: {saved}")

    def _profile_power_changed(self, online):
        previous = self._power_source
        self._power_source = online
        if not hasattr(self, "profile_source_state"):
            return
        if online is None:
            self.profile_source_state.set("Power source unavailable")
        elif previous is not None and previous != online:
            source = "ac" if online else "battery"
            selected = self.profile_prefs[source]
            if selected in self.profile_choices:
                self.set_profile(selected)
                self.profile_notice.set(f"Switched to your {source} profile: {selected.replace('-', ' ').title()}.")
            else:
                self.profile_notice.set(f"Your saved {source} profile is not exposed by this firmware.")
        self._render_profile_choices()

    def _overview(self, page):
        row = tk.Frame(page, bg=BG)
        row.pack(fill="x")
        self.cpu_card = self.card(row, "CPU Temperature", "Processor package")
        self.cpu_value = tk.StringVar(value="--")
        ttk.Label(self.cpu_card, textvariable=self.cpu_value, style="Hero.TLabel").pack(anchor="w")
        self.cpu_usage_value = tk.StringVar(value="CPU load  --%")
        tk.Label(self.cpu_card, textvariable=self.cpu_usage_value, bg=PANEL, fg=CYAN, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(4, 0))
        self.cpu_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.gpu_card = self.card(row, "GPU Temperature", "Discrete graphics")
        self.gpu_value = tk.StringVar(value="--")
        ttk.Label(self.gpu_card, textvariable=self.gpu_value, style="Hero.TLabel").pack(anchor="w")
        self.gpu_usage_value = tk.StringVar(value="GPU load  --%")
        tk.Label(self.gpu_card, textvariable=self.gpu_usage_value, bg=PANEL, fg=CYAN, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(4, 0))
        self.gpu_card.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.system_card = self.card(page, "System Information", "Live hardware and resource summary")
        grid = tk.Frame(self.system_card, bg=PANEL)
        grid.pack(fill="x")
        self.system_info = {key: tk.StringVar(value="Detecting…") for key in ("RAM", "STORAGE", "DEVICE MODEL", "CPU", "GPU")}
        for index, key in enumerate(self.system_info):
            tile = tk.Frame(grid, bg="#0c1219", padx=10, pady=9, highlightthickness=1, highlightbackground="#202b37")
            tile.grid(row=index // 3, column=index % 3, sticky="nsew", padx=(0, 6), pady=(0, 6))
            tk.Label(tile, text=key, bg="#0c1219", fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
            tk.Label(tile, textvariable=self.system_info[key], bg="#0c1219", fg=TEXT, font=("TkDefaultFont", 9, "bold"), anchor="w", justify="left", wraplength=220).pack(fill="x", anchor="w", pady=(4, 0))
        for column in range(3):
            grid.grid_columnconfigure(column, weight=1, uniform="system")
        self.system_card.pack(fill="x", pady=(10, 0))
        self.fan_card = self.card(page, "Fan Telemetry", "Current fan speeds reported by the embedded controller")
        self.fan_value = tk.StringVar(value="CPU  -- RPM     GPU  -- RPM")
        tk.Label(self.fan_card, textvariable=self.fan_value, bg=PANEL, fg=CYAN, font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
        self.fan_card.pack(fill="x", pady=12)
        profile_card = self.card(page, "Thermal Profiles", "AC and battery profiles are managed separately on the Profiles page.")
        self.active_profile = tk.StringVar(value=read(PROFILE / "profile", "unknown").replace("-", " ").title())
        tk.Label(profile_card, textvariable=self.active_profile, bg=PANEL, fg=CYAN, font=("TkDefaultFont", 13, "bold")).pack(side="left")
        ttk.Button(profile_card, text="Open Profiles", command=lambda: self.show_page("Profiles")).pack(side="right")
        profile_card.pack(fill="x")
        self.notice = tk.StringVar(value="")
        tk.Label(page, textvariable=self.notice, bg=BG, fg=MUTED, justify="left", wraplength=750).pack(anchor="w", pady=14)

    def _cooling(self, page):
        ttk.Label(page, text="Cooling", style="Title.TLabel").pack(anchor="w", pady=(0, 14))
        card = self.card(page, "Fan Control", "Choose automatic cooling, maximum fan speed, or tune both fans yourself.")
        speed = read(SENSE / "fan_speed", "0,0").split(",")
        try:
            cpu, gpu = map(int, speed[:2])
        except (ValueError, TypeError):
            cpu, gpu = 0, 0
        initial_mode = "Auto" if cpu == 0 and gpu == 0 else "Max" if cpu == 100 and gpu == 100 else "Custom"
        self.fan_mode = tk.StringVar(value=initial_mode)
        modes = tk.Frame(card, bg=PANEL2, padx=4, pady=4)
        modes.pack(fill="x", pady=(0, 14))
        self.fan_mode_buttons = {}
        for mode in ("Auto", "Max", "Custom"):
            button = ttk.Button(modes, text=mode, command=lambda value=mode: self.set_fan_mode(value))
            button.pack(side="left", fill="x", expand=True, padx=2)
            self.fan_mode_buttons[mode] = button

        rotor_row = tk.Frame(card, bg=PANEL)
        rotor_row.pack(fill="x", pady=(0, 12))
        self.fan_rotors = []
        self.fan_rpm = {"CPU": tk.StringVar(value="-- RPM"), "GPU": tk.StringVar(value="-- RPM")}
        for name in ("CPU", "GPU"):
            tile = tk.Frame(rotor_row, bg="#0c1219", padx=14, pady=10, highlightthickness=1, highlightbackground="#202b37")
            tile.pack(side="left", fill="both", expand=True, padx=(0, 8))
            canvas = tk.Canvas(tile, width=90, height=90, bg="#0c1219", highlightthickness=0)
            canvas.pack(side="left")
            tk.Label(tile, text=name, bg="#0c1219", fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=(8, 0))
            tk.Label(tile, textvariable=self.fan_rpm[name], bg="#0c1219", fg=TEXT, font=("TkDefaultFont", 13, "bold")).pack(anchor="w", padx=(8, 0), pady=(4, 0))
            self.fan_rotors.append((canvas, name))

        self.custom_fan_panel = tk.Frame(card, bg=PANEL)
        self.cpu_fan = tk.IntVar(value=max(1, min(100, cpu or 50)))
        self.gpu_fan = tk.IntVar(value=max(1, min(100, gpu or 50)))
        self._fan_slider(self.custom_fan_panel, "CPU fan", self.cpu_fan, 0)
        self._fan_slider(self.custom_fan_panel, "GPU fan", self.gpu_fan, 1)
        self.fan_status = tk.StringVar(value="Automatic fan control is active." if initial_mode == "Auto" else "Fans are set to maximum." if initial_mode == "Max" else "Custom fan control is active.")
        tk.Label(card, textvariable=self.fan_status, bg=PANEL, fg=CYAN, font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(10, 0))
        card.pack(fill="x")
        self.set_fan_mode(initial_mode, write_value=False)
        self._animate_fans()

    def _fan_slider(self, parent, label, var, row):
        line = tk.Frame(parent, bg=PANEL)
        line.pack(fill="x", pady=9)
        tk.Label(line, text=label, bg=PANEL, fg=TEXT, width=12, anchor="w").pack(side="left")
        ttk.Scale(line, from_=1, to=100, variable=var, command=lambda _v: self.apply_fans()).pack(side="left", fill="x", expand=True, padx=12)

    def apply_fans(self):
        if hasattr(self, "cpu_fan"):
            self.after_cancel(self._fan_after) if hasattr(self, "_fan_after") else None
            self._fan_after = self.after(350, self._commit_custom_fans)

    def _commit_custom_fans(self):
        if self.fan_mode.get() != "Custom":
            return
        value = f"{self.cpu_fan.get()},{self.gpu_fan.get()}"
        if write(SENSE / "fan_speed", value, "fan speed"):
            self.fan_status.set("Custom fan speeds applied.")

    def set_fan_mode(self, mode, write_value=True):
        if mode not in self.fan_mode_buttons:
            return
        self.fan_mode.set(mode)
        for name, button in self.fan_mode_buttons.items():
            button.configure(style="Accent.TButton" if name == mode else "TButton")
        if mode == "Custom":
            if self.cpu_fan.get() <= 0:
                self.cpu_fan.set(50)
            if self.gpu_fan.get() <= 0:
                self.gpu_fan.set(50)
            self.custom_fan_panel.pack(fill="x", pady=(4, 0))
            self.fan_status.set("Adjust each fan with its slider.")
            return
        self.custom_fan_panel.pack_forget()
        value = "0,0" if mode == "Auto" else "100,100"
        self.fan_status.set("Automatic fan control is active." if mode == "Auto" else "Fans are set to maximum.")
        if write_value and write(SENSE / "fan_speed", value, "fan speed"):
            self.cpu_fan.set(0 if mode == "Auto" else 100)
            self.gpu_fan.set(0 if mode == "Auto" else 100)

    def auto_fans(self):
        self.set_fan_mode("Auto")

    def max_fans(self):
        self.set_fan_mode("Max")

    def _animate_fans(self):
        if not hasattr(self, "fan_rotors"):
            return
        for canvas, name in self.fan_rotors:
            canvas.delete("all")
            width, height = max(canvas.winfo_width(), 90), max(canvas.winfo_height(), 90)
            cx, cy, radius = width / 2, height / 2, min(width, height) * 0.44
            canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, outline="#253341", width=2)
            rpm_text = self.fan_rpm[name].get().split()[0]
            try:
                rpm = int(rpm_text)
            except ValueError:
                rpm = 500
            rotation = (time.monotonic() * max(90, min(900, rpm / 4))) % 360
            blade = ((0.08, -0.06), (0.33, -0.18), (0.39, -0.02), (0.20, 0.12), (0.10, 0.08))
            for blade_index in range(4):
                angle = math.radians(rotation + blade_index * 90)
                coords = []
                for bx, by in blade:
                    x = bx * math.cos(angle) - by * math.sin(angle)
                    y = bx * math.sin(angle) + by * math.cos(angle)
                    coords.extend((cx + x * radius * 2, cy + y * radius * 2))
                canvas.create_polygon(*coords, fill=ACCENT if name == "CPU" else "#8c74ff", outline="")
            canvas.create_oval(cx-7, cy-7, cx+7, cy+7, fill="#ecf6fa", outline="")
        self.after(60, self._animate_fans)

    def _lighting(self, page):
        ttk.Label(page, text="Lighting", style="Title.TLabel").pack(anchor="w", pady=(0, 3))
        tk.Label(page, text="Personalize the four-zone keyboard backlight.", bg=BG, fg=MUTED, font=("TkDefaultFont", 9)).pack(anchor="w", pady=(0, 13))
        # Keyboard controls are siblings of predator_sense/nitro_sense.
        self.backlight_dir = BASE / "four_zoned_kb"
        effect = read(self.backlight_dir / "four_zone_mode", "0,5,100,0,255,40,40").split(",")
        try:
            if len(effect) != 7:
                raise ValueError
            mode, speed, brightness, direction, red, green, blue = map(int, effect)
            if not (0 <= mode <= 7 and 0 <= speed <= 9 and 0 <= brightness <= 100 and 0 <= direction <= 2 and all(0 <= c <= 255 for c in (red, green, blue))):
                raise ValueError
        except ValueError:
            mode, speed, brightness, direction, red, green, blue = 0, 5, 100, 0, 255, 40, 40
        current = read(self.backlight_dir / "per_zone_mode", "").split(",")
        initial = current[:4] if len(current) >= 5 else ["ff303f"] * 4
        initial = [c.strip().lstrip("#") for c in initial]
        if any(len(c) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in c) for c in initial):
            initial = ["ff303f"] * 4
        try:
            zone_brightness = str(max(0, min(100, int(current[4])))) if len(current) >= 5 else str(brightness)
        except ValueError:
            zone_brightness = str(brightness)

        self.effect_mode = tk.StringVar(value=str(mode))
        if mode == 0:
            self.effect_mode.set("1")
        self.effect_speed = tk.IntVar(value=speed)
        self.effect_brightness = tk.StringVar(value=str(brightness))
        # Firmware's direction enum is reversed on the tested keyboard: 1 runs
        # rightward and 2 runs leftward. Keep UI values intuitive and translate
        # at the sysfs boundary.
        self.effect_direction = tk.StringVar(value=str(3 - direction if direction in (1, 2) else 1))
        self.effect_color = tk.StringVar(value=f"{red},{green},{blue}")
        self.effect_status = tk.StringVar(value=f"Firmware: {self._effect_name(mode)}")
        self.zone_vars = [tk.StringVar(value=f"#{color}") for color in initial]
        self.zone_brightness = tk.StringVar(value=zone_brightness)
        self.effect_brightness.set(zone_brightness if mode == 0 else str(brightness))
        self.zone_selected = tk.IntVar(value=0)
        self.lighting_mode = tk.StringVar(value="Dynamic" if mode else "Static")
        self.zone_status = tk.StringVar(value="Select a zone, choose a color, then apply.")
        self.lighting_status = tk.StringVar(value=f"Firmware: {self._effect_name(mode)}")

        workspace = tk.Frame(page, bg=BG)
        workspace.pack(fill="both", expand=True)
        preview = tk.Frame(workspace, bg=PANEL, padx=17, pady=15, highlightthickness=1, highlightbackground="#252c38")
        preview.pack(side="left", fill="both", expand=True, padx=(0, 10))
        preview_head = tk.Frame(preview, bg=PANEL)
        preview_head.pack(fill="x", pady=(0, 10))
        tk.Label(preview_head, text="FOUR-ZONE KEYBOARD", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(side="left")
        tk.Label(preview_head, text="●  CONNECTED", bg=PANEL, fg=GREEN, font=("TkDefaultFont", 8, "bold")).pack(side="right")
        self.kb_canvas = tk.Canvas(preview, height=320, bg="#080c11", highlightthickness=1, highlightbackground="#252c38")
        self.kb_canvas.pack(fill="x", expand=True)
        self.kb_canvas.bind("<Configure>", lambda event: self._draw_keyboard(event.width, event.height))
        tk.Label(preview, text="Click a key to select its lighting zone.", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8)).pack(anchor="w", pady=(9, 0))

        settings = tk.Frame(workspace, bg=PANEL, width=300, padx=16, pady=16, highlightthickness=1, highlightbackground="#252c38")
        settings.pack(side="right", fill="y")
        settings.pack_propagate(False)
        self.lighting_settings = settings
        tk.Label(settings, text="LIGHTING PROFILE", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")

        mode_row = tk.Frame(settings, bg=PANEL2, padx=3, pady=3)
        mode_row.pack(fill="x", pady=(6, 8))
        self.mode_static_button = ttk.Button(mode_row, text="Static", command=lambda: self.set_lighting_mode("Static"))
        self.mode_static_button.pack(side="left", fill="x", expand=True)
        self.mode_dynamic_button = ttk.Button(mode_row, text="Dynamic", command=lambda: self.set_lighting_mode("Dynamic"))
        self.mode_dynamic_button.pack(side="left", fill="x", expand=True)
        self.mode_buttons = (self.mode_static_button, self.mode_dynamic_button)

        self.static_controls = tk.Frame(settings, bg=PANEL)
        tk.Label(self.static_controls, text="STATIC COLOR LAYOUT", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(0, 4))
        layout_row = tk.Frame(self.static_controls, bg=PANEL2, padx=3, pady=3)
        layout_row.pack(fill="x", pady=(0, 8))
        self.static_layout = tk.StringVar(value="Four Zone")
        self.four_zone_button = ttk.Button(layout_row, text="Four Zone", command=lambda: self.set_static_layout("Four Zone"))
        self.four_zone_button.pack(side="left", fill="x", expand=True)
        self.single_zone_button = ttk.Button(layout_row, text="Single Zone", command=lambda: self.set_static_layout("Single Zone"))
        self.single_zone_button.pack(side="left", fill="x", expand=True)
        self.layout_buttons = (self.four_zone_button, self.single_zone_button)

        self.selected_zone_text = tk.StringVar(value="Zone 1 selected")
        tk.Label(self.static_controls, text="SELECTED ZONE", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
        tk.Label(self.static_controls, textvariable=self.selected_zone_text, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(2, 4))
        self.selected_swatch = tk.Frame(self.static_controls, bg=self.zone_vars[0].get(), height=22, highlightthickness=1, highlightbackground="#3d4858")
        self.selected_swatch.pack(fill="x", pady=(0, 5))
        self.selected_rgb = tk.StringVar(value=self._rgb_text(self.zone_vars[0].get()))
        tk.Label(self.static_controls, textvariable=self.selected_rgb, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 9)).pack(anchor="w", pady=(0, 5))
        ttk.Button(self.static_controls, text="Choose zone color…", command=self.choose_selected_zone_color).pack(fill="x")

        tk.Label(self.static_controls, text="BRIGHTNESS", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(8, 2))
        self.zone_brightness_text = tk.StringVar(value=f"{self.zone_brightness.get()}%")
        ttk.Scale(self.static_controls, from_=0, to=100, variable=self.zone_brightness, command=self._brightness_changed).pack(fill="x")
        tk.Label(self.static_controls, textvariable=self.zone_brightness_text, bg=PANEL, fg=CYAN, font=("TkDefaultFont", 9, "bold")).pack(anchor="e")

        self.dynamic_controls = tk.Frame(settings, bg=PANEL)
        self.dynamic_controls.pack(fill="x", pady=(7, 0))
        ttk.Label(self.dynamic_controls, text="Effect", style="Muted.TLabel").pack(anchor="w")
        effect_tabs = tk.Frame(self.dynamic_controls, bg=PANEL)
        effect_tabs.pack(fill="x", pady=(5, 4))
        effects = (("1", "Breathe", ("#35c8ff", "#815dff")), ("2", "Neon", ("#ff4f9a", "#7d53ff")), ("3", "Wave", ("#20d9c2", "#3683ff")), ("4", "Shift", ("#ff8b42", "#ee4a78")), ("5", "Zoom", ("#b6e84e", "#28c7a0")), ("6", "Meteor", ("#ffbd4a", "#fa5b52")), ("7", "Twinkle", ("#9a72ff", "#34c7e5")))
        self.effect_buttons = {}
        for index, (value, title, colors) in enumerate(effects):
            button = GradientButton(effect_tabs, title, lambda selected=value: self.select_effect(selected), colors, width=58, height=34)
            button.grid(row=index // 4, column=index % 4, padx=(0, 5), pady=4, sticky="ew")
            effect_tabs.grid_columnconfigure(index % 4, weight=1, uniform="effect-tabs")
            self.effect_buttons[value] = button
        self.effect_parameters = tk.Frame(self.dynamic_controls, bg=PANEL)
        self.effect_parameters.pack(fill="x", pady=(2, 4))
        speed_box = tk.Frame(self.effect_parameters, bg=PANEL)
        speed_box.pack(fill="x", pady=(0, 5))
        tk.Label(speed_box, text="SPEED", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
        self.effect_speed_control = ttk.Scale(speed_box, from_=0, to=9, variable=self.effect_speed, command=self._effect_speed_changed)
        self.effect_speed_control.pack(fill="x", pady=(1, 0))
        self.effect_direction_row = tk.Frame(self.effect_parameters, bg=PANEL)
        self.effect_direction_row.pack(fill="x")
        tk.Label(self.effect_direction_row, text="DIRECTION", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
        direction_buttons = tk.Frame(self.effect_direction_row, bg=PANEL)
        direction_buttons.pack(fill="x", pady=(2, 0))
        for column in range(2):
            direction_buttons.grid_columnconfigure(column, weight=1, uniform="direction")
        self.direction_buttons = {}
        for column, (value, label) in enumerate((("1", "← Left"), ("2", "Right →"))):
            button = ttk.Button(direction_buttons, text=label, command=lambda selected=value: self.select_effect_direction(selected), padding=(2, 3))
            button.grid(row=0, column=column, sticky="ew", padx=(0, 4 if column == 0 else 0))
            self.direction_buttons[value] = button
        self.effect_color_row = self._color_picker_row(self.dynamic_controls, "Effect color", self.effect_color)
        tk.Label(self.dynamic_controls, text="EFFECT BRIGHTNESS", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(2, 0))
        ttk.Scale(self.dynamic_controls, from_=0, to=100, variable=self.effect_brightness, command=self._brightness_changed).pack(fill="x")
        self.effect_mode.trace_add("write", lambda *_args: self._update_effect_controls())
        self._update_effect_controls()

        self.apply_lighting_button = ttk.Button(settings, text="APPLY LIGHTING", style="Accent.TButton", command=self.apply_lighting)
        self.apply_lighting_button.pack(fill="x", pady=(8, 5))
        self.lighting_status_label = tk.Label(settings, textvariable=self.lighting_status, bg=PANEL, fg=CYAN, wraplength=255, justify="left", font=("TkDefaultFont", 8, "bold"))
        self.lighting_status_label.pack(anchor="w")

        self.zone_rgb_labels = []
        self._zone_chips = []
        zone_strip = tk.Frame(preview, bg=PANEL)
        zone_strip.pack(fill="x", pady=(14, 0))
        for index, color_var in enumerate(self.zone_vars):
            zone_card = tk.Frame(zone_strip, bg="#0e141b", padx=9, pady=8, highlightthickness=1, highlightbackground="#252c38")
            zone_card.pack(side="left", fill="both", expand=True, padx=(0 if index == 0 else 5, 0))
            tk.Label(zone_card, text=f"ZONE {index + 1}", bg="#0e141b", fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
            chip = tk.Frame(zone_card, bg=color_var.get(), height=15)
            chip.pack(fill="x", pady=(6, 4))
            self._zone_chips.append(chip)
            rgb_label = tk.StringVar(value=self._rgb_text(color_var.get()))
            self.zone_rgb_labels.append(rgb_label)
            tk.Label(zone_card, textvariable=rgb_label, bg="#0e141b", fg=TEXT, font=("TkDefaultFont", 8)).pack(anchor="w")
            ttk.Button(zone_card, text="Color", command=lambda n=index: self.choose_zone_color(n)).pack(fill="x", pady=(6, 0))
            zone_card.bind("<Button-1>", lambda _event, n=index: self.select_zone(n))

        self.set_lighting_mode(self.lighting_mode.get())
        self._draw_keyboard()
        self.timeout_var = tk.BooleanVar(value=read(SENSE / "backlight_timeout", "0") == "1")
        timeout_card = tk.Frame(page, bg=PANEL, padx=14, pady=10, highlightthickness=1, highlightbackground="#252c38")
        timeout_card.pack(fill="x", pady=(9, 0))
        timeout_copy = tk.Frame(timeout_card, bg=PANEL)
        timeout_copy.pack(side="left", fill="x", expand=True)
        tk.Label(timeout_copy, text="Keyboard backlight timeout", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        tk.Label(timeout_copy, text="Turn lighting off after 30 seconds idle", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8)).pack(anchor="w", pady=(2, 0))
        self.timeout_state = tk.StringVar()
        tk.Label(timeout_card, textvariable=self.timeout_state, bg=PANEL, fg=CYAN, font=("TkDefaultFont", 8, "bold")).pack(side="right", padx=(10, 8))
        self.timeout_switch = tk.Canvas(timeout_card, width=52, height=28, bg=PANEL, highlightthickness=0, cursor="hand2")
        self.timeout_switch.pack(side="right")
        self.timeout_switch.bind("<Button-1>", self._toggle_timeout)
        self._render_timeout_switch()

    def _labeled_combo(self, parent, label, var, values):
        line = tk.Frame(parent, bg=PANEL)
        line.pack(fill="x", pady=5)
        tk.Label(line, text=label, bg=PANEL, fg=MUTED, width=12, anchor="w").pack(side="left")
        labels = [f"{key} — {name}" for key, name in values]
        display = tk.StringVar(value=next((label for (key, _), label in zip(values, labels) if key == var.get()), labels[0]))
        combo = ttk.Combobox(line, textvariable=display, state="readonly", values=labels, width=16)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda _event: var.set(values[labels.index(display.get())][0]))
        return line, combo

    def _labeled_entry(self, parent, label, var):
        line = tk.Frame(parent, bg=PANEL)
        line.pack(fill="x", pady=5)
        tk.Label(line, text=label, bg=PANEL, fg=MUTED, width=17, anchor="w").pack(side="left")
        ttk.Entry(line, textvariable=var, width=24).pack(side="left")

    @staticmethod
    def _hex_to_rgb(color):
        value = color.strip().lstrip("#")
        if len(value) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
            return (255, 48, 63)
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))

    def _color_picker_row(self, parent, title, rgb_var):
        line = tk.Frame(parent, bg=PANEL)
        line.pack(fill="x", pady=5)
        color_info = tk.Frame(line, bg=PANEL)
        color_info.pack(fill="x")
        tk.Label(color_info, text=title.upper(), bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(side="left")
        rgb = tuple(int(part) for part in rgb_var.get().split(","))
        self.effect_swatch = tk.Frame(color_info, bg="#%02x%02x%02x" % rgb, width=28, height=18, highlightthickness=1, highlightbackground="#64748b")
        self.effect_swatch.pack(side="right", padx=(6, 0))
        self.effect_rgb_label = tk.StringVar(value=f"R{rgb[0]} G{rgb[1]} B{rgb[2]}")
        tk.Label(color_info, textvariable=self.effect_rgb_label, bg=PANEL, fg=TEXT, anchor="e", font=("TkDefaultFont", 8, "bold")).pack(side="right")
        ttk.Button(line, text="Choose effect color…", command=lambda: self._choose_effect_color(rgb_var), padding=(5, 4)).pack(fill="x", pady=(5, 0))
        return line

    def _update_effect_controls(self):
        if not hasattr(self, "effect_direction_row"):
            return
        mode = self.effect_mode.get()
        color_supported = mode != "2"
        self.effect_color_row.pack_forget()
        if self.effect_direction.get() not in ("1", "2"):
            self.effect_direction.set("1")
        for value, button in self.direction_buttons.items():
            button.configure(style="Accent.TButton" if self.effect_direction.get() == value else "TButton")
        if color_supported:
            self.effect_color_row.pack(fill="x", pady=5)
        for value, button in self.effect_buttons.items():
            button.set_active(value == mode)

    def select_effect(self, mode):
        self.effect_mode.set(mode)

    def select_effect_direction(self, direction):
        self.effect_direction.set(direction)
        for value, button in self.direction_buttons.items():
            button.configure(style="Accent.TButton" if value == direction else "TButton")

    def _effect_speed_changed(self, value):
        speed = max(0, min(9, round(float(value))))
        self.effect_speed.set(speed)

    def _choose_effect_color(self, rgb_var):
        current = tuple(int(part) for part in rgb_var.get().split(","))
        rgb = self._ask_color("Effect color", "#%02x%02x%02x" % current)
        if rgb:
            rgb_var.set(",".join(map(str, rgb)))
            color = "#%02x%02x%02x" % rgb
            self.effect_swatch.configure(bg=color)
            self.effect_rgb_label.set(f"R{rgb[0]} G{rgb[1]} B{rgb[2]}")

    def _choose_zone_color(self, zone, color_var, swatch, rgb_label):
        rgb = self._ask_color(f"Zone {zone} color", color_var.get())
        if rgb:
            color = "#%02x%02x%02x" % rgb
            color_var.set(color)
            swatch.configure(bg=color)
            rgb_label.set(f"R {rgb[0]}   G {rgb[1]}   B {rgb[2]}")
            self._sync_zone_display(zone)

    def _ask_color(self, title, initial):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()
        tk.Label(dialog, text=title.upper(), bg=BG, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(dialog, text="Pick a hue and saturation from the color wheel.", bg=BG, fg=MUTED, font=("TkDefaultFont", 9)).pack(anchor="w", padx=20, pady=(0, 10))
        content = tk.Frame(dialog, bg=BG)
        content.pack(padx=18)
        size, radius = 294, 124
        wheel = tk.Canvas(content, width=size, height=size, bg=BG, highlightthickness=0, cursor="crosshair")
        wheel.pack(side="left", padx=(0, 15))
        red, green, blue = self._hex_to_rgb(initial)
        hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
        bright = tk.DoubleVar(value=value * 100)
        rgb_text = tk.StringVar()
        rgb_vars = [tk.IntVar(value=channel) for channel in (red, green, blue)]
        syncing_rgb = False
        color_controls = tk.Frame(content, bg=BG)
        color_controls.pack(side="right", fill="y", pady=(9, 0))
        preview = tk.Canvas(color_controls, width=100, height=74, bg=PANEL, highlightthickness=1, highlightbackground="#465366")
        preview.pack(anchor="n")
        for index, name in enumerate(("R", "G", "B")):
            line = tk.Frame(color_controls, bg=BG)
            line.pack(fill="x", pady=(10, 0))
            tk.Label(line, text=name, bg=BG, fg=TEXT, width=2, font=("TkDefaultFont", 9, "bold")).pack(side="left")
            ttk.Scale(line, from_=0, to=255, variable=rgb_vars[index], command=lambda channel, n=index: rgb_vars[n].set(round(float(channel)))).pack(side="left", fill="x", expand=True, padx=4)
            tk.Spinbox(line, from_=0, to=255, increment=1, textvariable=rgb_vars[index], width=4, justify="center", bg=PANEL2, fg=TEXT, buttonbackground="#344255", insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground="#344255").pack(side="right")

        def draw_wheel():
            nonlocal syncing_rgb
            wheel.delete("all")
            center = size / 2
            box = (center - radius, center - radius, center + radius, center + radius)
            brightness = max(0.01, min(1, bright.get() / 100))
            for degree in range(0, 360, 3):
                color = "#%02x%02x%02x" % tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(degree / 360, 1, brightness))
                wheel.create_arc(*box, start=degree, extent=3.5, style=tk.PIESLICE, fill=color, outline=color)
            wheel.create_oval(center - radius * 0.36, center - radius * 0.36, center + radius * 0.36, center + radius * 0.36, fill="#f4f7fa", outline="#ffffff", width=2)
            angle = math.radians(hue * 360)
            marker_radius = saturation * radius
            mx = center + math.cos(angle) * marker_radius
            my = center - math.sin(angle) * marker_radius
            wheel.create_oval(mx - 8, my - 8, mx + 8, my + 8, fill="#10151d", outline="#ffffff", width=3)
            color_rgb = tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, saturation, bright.get() / 100))
            color = "#%02x%02x%02x" % color_rgb
            preview.delete("all")
            preview.create_rectangle(3, 3, 97, 71, fill=color, outline="")
            syncing_rgb = True
            for variable, channel in zip(rgb_vars, color_rgb):
                variable.set(channel)
            syncing_rgb = False
            rgb_text.set(f"R {color_rgb[0]}    G {color_rgb[1]}    B {color_rgb[2]}")

        def rgb_edited(*_args):
            nonlocal hue, saturation
            if syncing_rgb:
                return
            try:
                channels = tuple(max(0, min(255, int(variable.get()))) for variable in rgb_vars)
            except (ValueError, tk.TclError):
                return
            hue, saturation, brightness_value = colorsys.rgb_to_hsv(*(channel / 255 for channel in channels))
            bright.set(brightness_value * 100)
            draw_wheel()

        for variable in rgb_vars:
            variable.trace_add("write", rgb_edited)

        def select_point(event):
            nonlocal hue, saturation
            center = size / 2
            dx, dy = event.x - center, center - event.y
            hue = math.atan2(dy, dx) % (2 * math.pi) / (2 * math.pi)
            saturation = min(1, math.hypot(dx, dy) / radius)
            draw_wheel()

        wheel.bind("<Button-1>", select_point)
        wheel.bind("<B1-Motion>", select_point)
        slider_line = tk.Frame(dialog, bg=BG)
        slider_line.pack(fill="x", padx=22, pady=(8, 2))
        tk.Label(slider_line, text="BRIGHTNESS", bg=BG, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
        ttk.Scale(slider_line, from_=0, to=100, variable=bright, command=lambda _value: draw_wheel()).pack(fill="x", pady=(3, 0))
        tk.Label(dialog, textvariable=rgb_text, bg=BG, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(anchor="center", pady=8)
        buttons = tk.Frame(dialog, bg=BG)
        buttons.pack(fill="x", padx=20, pady=(3, 18))
        result = []

        def accept():
            result.extend(self._hex_to_rgb(preview_color()))
            dialog.destroy()

        def preview_color():
            return "#%02x%02x%02x" % tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, saturation, bright.get() / 100))

        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Use color", style="Accent.TButton", command=accept).pack(side="right", padx=(0, 8))
        draw_wheel()
        dialog.wait_window()
        return tuple(result) if result else None

    @staticmethod
    def _rgb_text(color):
        red, green, blue = SenseApp._hex_to_rgb(color)
        return f"R {red}   G {green}   B {blue}"

    def _sync_zone_display(self, zone):
        color = self.zone_vars[zone].get()
        if hasattr(self, "_zone_chips") and zone < len(self._zone_chips):
            self._zone_chips[zone].configure(bg=color)
        if hasattr(self, "zone_rgb_labels") and zone < len(self.zone_rgb_labels):
            self.zone_rgb_labels[zone].set(self._rgb_text(color))
        if self.zone_selected.get() == zone and hasattr(self, "selected_swatch"):
            self.selected_swatch.configure(bg=color)
            self.selected_rgb.set(self._rgb_text(color))
        self._draw_keyboard()

    def _draw_keyboard(self, width=None, height=None):
        if not hasattr(self, "kb_canvas") or not self.kb_canvas.winfo_exists():
            return
        canvas = self.kb_canvas
        canvas.delete("all")
        width = width or max(canvas.winfo_width(), 600)
        height = height or max(canvas.winfo_height(), 280)
        canvas.create_text(22, 18, text="PRED SENSE  /  FOUR-ZONE RGB", anchor="w", fill="#697585", font=("TkDefaultFont", 8, "bold"))
        rows = [
            [("ESC", 1), *[(f"F{i}", 1) for i in range(1, 13)], ("DEL", 1)],
            [("~", 1), *[(str(i), 1) for i in range(1, 10)], ("0", 1), ("-", 1), ("=", 1), ("BACK", 2)],
            [("TAB", 1.5), *list("QWERTYUIOP"), ("[", 1), ("]", 1), ("\\", 1.5)],
            [("CAPS", 1.8), *list("ASDFGHJKL"), (";", 1), ("'", 1), ("ENTER", 2.2)],
            [("SHIFT", 2.3), *list("ZXCVBNM"), (",", 1), (".", 1), ("/", 1), ("SHIFT", 2.6)],
            [("CTRL", 1.3), ("FN", 1), ("WIN", 1.2), ("ALT", 1.2), ("SPACE", 5.8), ("ALT", 1.2), ("←", 1), ("↓", 1), ("→", 1)],
        ]
        key_gap, row_gap, key_h = 5, 9, 25
        max_units = max(sum(item[1] if isinstance(item, tuple) else 1 for item in row) for row in rows)
        unit = min(38, (width - 42 - (len(rows[1]) - 1) * key_gap) / max_units)
        total_h = len(rows) * key_h + (len(rows) - 1) * row_gap
        y_start = max(44, (height - total_h) / 2)
        zone_width = (width - 34) / 4
        for row_index, row in enumerate(rows):
            units = sum(item[1] if isinstance(item, tuple) else 1 for item in row)
            gaps = (len(row) - 1) * key_gap
            x = (width - (units * unit + gaps)) / 2
            y = y_start + row_index * (key_h + row_gap)
            for item in row:
                label, factor = item if isinstance(item, tuple) else (item, 1)
                key_w = unit * factor
                zone = min(3, max(0, int((x + key_w / 2 - 17) / zone_width)))
                fill = self.zone_vars[zone].get()
                self.kb_canvas.create_rectangle(x, y, x + key_w, y + key_h, fill="#101821", outline=fill, width=2, tags=(f"zone{zone}", "key"))
                self.kb_canvas.create_text(x + key_w / 2, y + key_h / 2, text=label, fill="#c2cbd5", font=("TkDefaultFont", 7), tags=(f"zone{zone}", "key"))
                x += key_w + key_gap
        for zone in range(4):
            x = 17 + zone * zone_width
            self.kb_canvas.create_line(x, height - 26, x + zone_width - 8, height - 26, fill=self.zone_vars[zone].get(), width=3)
            self.kb_canvas.create_text(x + (zone_width - 8) / 2, height - 12, text=f"ZONE {zone + 1}", fill="#9aa7b5", font=("TkDefaultFont", 7, "bold"))
            self.kb_canvas.tag_bind(f"zone{zone}", "<Button-1>", lambda _event, n=zone: self.select_zone(n))

    def select_zone(self, zone):
        if self.static_layout.get() == "Single Zone":
            zone = 0
        self.zone_selected.set(zone)
        self.selected_zone_text.set("All four zones" if self.static_layout.get() == "Single Zone" else f"Zone {zone + 1} selected")
        self.selected_swatch.configure(bg=self.zone_vars[zone].get())
        self.selected_rgb.set(self._rgb_text(self.zone_vars[zone].get()))

    def choose_zone_color(self, zone):
        if self.static_layout.get() == "Single Zone":
            zone = 0
        self._choose_zone_color(zone, self.zone_vars[zone], self._zone_chips[zone], self.zone_rgb_labels[zone])
        if self.static_layout.get() == "Single Zone":
            color = self.zone_vars[0].get()
            for index in range(1, 4):
                self.zone_vars[index].set(color)
                self._sync_zone_display(index)

    def choose_selected_zone_color(self):
        self.choose_zone_color(self.zone_selected.get())

    def _brightness_changed(self, value):
        brightness = max(0, min(100, round(float(value))))
        self.zone_brightness.set(str(brightness))
        self.effect_brightness.set(str(brightness))
        self.zone_brightness_text.set(f"{brightness}%")

    def set_lighting_mode(self, mode):
        self.lighting_mode.set(mode)
        self.mode_static_button.configure(style="Accent.TButton" if mode == "Static" else "TButton")
        self.mode_dynamic_button.configure(style="Accent.TButton" if mode == "Dynamic" else "TButton")
        for button in self.layout_buttons:
            button.configure(state="normal" if mode == "Static" else "disabled")
        self.four_zone_button.configure(style="Accent.TButton" if self.static_layout.get() == "Four Zone" else "TButton")
        self.single_zone_button.configure(style="Accent.TButton" if self.static_layout.get() == "Single Zone" else "TButton")
        if mode == "Dynamic":
            self.static_controls.pack_forget()
            self.dynamic_controls.pack(fill="x", pady=(7, 0))
        else:
            self.dynamic_controls.pack_forget()
            self.static_controls.pack(fill="x", pady=(0, 4))
        if hasattr(self, "lighting_status"):
            self.lighting_status.set(self.zone_status.get() if mode == "Static" else self.effect_status.get())

    def set_static_layout(self, layout):
        self.static_layout.set(layout)
        self.four_zone_button.configure(style="Accent.TButton" if layout == "Four Zone" else "TButton")
        self.single_zone_button.configure(style="Accent.TButton" if layout == "Single Zone" else "TButton")
        if layout == "Single Zone":
            self.zone_selected.set(0)
            self.selected_zone_text.set("All four zones")
            shared_color = self.zone_vars[0].get()
            for index in range(1, 4):
                self.zone_vars[index].set(shared_color)
                self._sync_zone_display(index)
        else:
            self.selected_zone_text.set(f"Zone {self.zone_selected.get() + 1} selected")
        self._sync_zone_display(0)

    def apply_lighting(self):
        if self.lighting_mode.get() == "Dynamic":
            self.apply_effect()
            self.lighting_status.set(self.effect_status.get())
        else:
            self.apply_zones()
            self.lighting_status.set(self.zone_status.get())

    def _power(self, page):
        ttk.Label(page, text="Power & Battery", style="Title.TLabel").pack(anchor="w", pady=(0, 14))
        battery = self.card(page, "Battery health", "Limit charge to around 80% for laptops that spend long periods connected to AC power.")
        self.limiter_var = tk.BooleanVar(value=read(SENSE / "battery_limiter", "0") == "1")
        ttk.Checkbutton(battery, text="Enable battery charge limiter", variable=self.limiter_var, command=self.set_limiter).pack(anchor="w", pady=6)
        self.calibration_var = tk.StringVar(value=read(SENSE / "battery_calibration", "0"))
        controls = tk.Frame(battery, bg=PANEL)
        controls.pack(fill="x", pady=(12, 0))
        tk.Label(controls, text="Calibration", bg=PANEL, fg=MUTED).pack(side="left")
        ttk.Button(controls, text="Start", command=lambda: self.calibrate("1")).pack(side="left", padx=(12, 5))
        ttk.Button(controls, text="Stop", command=lambda: self.calibrate("0")).pack(side="left")
        tk.Label(battery, text="Calibration can take a long time. Keep AC connected for the full process.", bg=PANEL, fg=MUTED, wraplength=650).pack(anchor="w", pady=(12, 0))
        battery.pack(fill="x")
        usb = self.card(page, "USB charging while powered off", "Choose the battery level at which USB charging stops.")
        self.usb_var = tk.StringVar(value=read(SENSE / "usb_charging", "0"))
        self._labeled_combo(usb, "Stop at", self.usb_var, [("0", "Disabled"), ("10", "10%"), ("20", "20%"), ("30", "30%")])
        ttk.Button(usb, text="Apply", command=self.set_usb).pack(anchor="e", pady=(10, 0))
        usb.pack(fill="x", pady=12)
        misc = self.card(page, "Boot & display", "These firmware options are available only on supported models.")
        self.boot_var = tk.BooleanVar(value=read(SENSE / "boot_animation_sound", "0") == "1")
        self.lcd_var = tk.BooleanVar(value=read(SENSE / "lcd_override", "0") == "1")
        ttk.Checkbutton(misc, text="Boot animation and sound", variable=self.boot_var, command=lambda: write(SENSE / "boot_animation_sound", int(self.boot_var.get()), "boot animation and sound")).pack(anchor="w", pady=4)
        ttk.Checkbutton(misc, text="LCD response override", variable=self.lcd_var, command=lambda: write(SENSE / "lcd_override", int(self.lcd_var.get()), "LCD override")).pack(anchor="w", pady=4)
        misc.pack(fill="x")

    def set_profile(self, value=None):
        value = value or self.profile_prefs.get("ac", "balanced")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(3)
                client.connect(PROFILE_SOCKET)
                client.sendall((json.dumps({"action": "set_profile", "profile": value}) + "\n").encode())
                response = json.loads(client.makefile("rb").readline(1024))
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "Profile change failed."))
            self._last_applied_profile = value
            if hasattr(self, "active_profile"):
                self.active_profile.set(value.replace("-", " ").title())
            if hasattr(self, "profile_notice"):
                self.profile_notice.set(f"Applied {value.replace('-', ' ').title()}.")
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("PredSenseLinux", f"Could not apply profile. Check that the profile helper is running.\n\n{exc}")

    def set_limiter(self):
        write(SENSE / "battery_limiter", int(self.limiter_var.get()), "battery limiter")

    def calibrate(self, value):
        if value == "1" and not messagebox.askyesno("Battery calibration", "Start battery calibration? Keep AC connected until calibration is complete."):
            return
        if write(SENSE / "battery_calibration", value, "battery calibration"):
            self.calibration_var.set(value)

    def set_usb(self):
        if not self.usb_var.get().isdigit() or int(self.usb_var.get()) not in (0, 10, 20, 30):
            messagebox.showerror("USB charging", "Choose Disabled, 10%, 20%, or 30%.")
            return
        write(SENSE / "usb_charging", self.usb_var.get(), "USB charging")

    def set_timeout(self):
        write(SENSE / "backlight_timeout", int(self.timeout_var.get()), "backlight timeout")

    def _render_timeout_switch(self):
        if not hasattr(self, "timeout_switch"):
            return
        enabled = self.timeout_var.get()
        canvas = self.timeout_switch
        canvas.delete("all")
        color = ACCENT if enabled else "#394351"
        canvas.create_oval(2, 3, 50, 25, fill=color, outline="")
        x = 37 if enabled else 15
        canvas.create_oval(x - 8, 5, x + 8, 21, fill="#f4f7fa", outline="")
        self.timeout_state.set("ON" if enabled else "OFF")

    def _toggle_timeout(self, _event=None):
        self.timeout_var.set(not self.timeout_var.get())
        self._render_timeout_switch()
        self.set_timeout()

    @staticmethod
    def _cpu_model():
        try:
            for line in pathlib.Path("/proc/cpuinfo").read_text(errors="ignore").splitlines():
                if line.lower().startswith(("model name", "hardware")):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
        return "Unknown CPU"

    @staticmethod
    def _memory_summary():
        try:
            values = {}
            for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
                if ":" not in line:
                    continue
                key, raw = line.split(":", 1)
                values[key] = int(raw.strip().split()[0]) * 1024
            total = values["MemTotal"]
            available = values["MemAvailable"]
            used = total - available
            return f"{used / 1024**3:.1f} / {total / 1024**3:.1f} GB used  ·  {used / total * 100:.0f}%"
        except (OSError, KeyError, ValueError, ZeroDivisionError):
            return "Unavailable"

    @staticmethod
    def _gpu_model():
        if NVIDIA_SMI:
            try:
                result = subprocess.run([NVIDIA_SMI, "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True, timeout=2, check=True)
                name = result.stdout.strip().splitlines()[0]
                if name:
                    return name
            except (OSError, subprocess.SubprocessError, IndexError):
                pass
        try:
            result = subprocess.run(["lspci", "-mm"], capture_output=True, text=True, timeout=2, check=True)
            devices = [shlex.split(line) for line in result.stdout.splitlines()]
            names = [" ".join(device[2:4]) for device in devices if len(device) >= 3 and device[1] in ("VGA compatible controller", "3D controller")]
            return " / ".join(names) if names else "Unavailable"
        except (OSError, subprocess.SubprocessError, IndexError):
            return "Unavailable"

    def _system_snapshot(self):
        if not hasattr(self, "_static_hardware"):
            self._static_hardware = {
                "DEVICE MODEL": read("/sys/class/dmi/id/product_name", "Unknown device").strip(),
                "CPU": self._cpu_model(),
                "GPU": self._gpu_model(),
            }
        try:
            usage = shutil.disk_usage("/")
            storage = f"{(usage.total - usage.free) / 1024**3:.0f} / {usage.total / 1024**3:.0f} GB used"
        except OSError:
            storage = "Unavailable"
        return {"RAM": self._memory_summary(), "STORAGE": storage, **self._static_hardware}

    def apply_effect(self):
        try:
            rgb = [int(part.strip()) for part in self.effect_color.get().split(",")]
            mode, speed, brightness, direction = map(int, (self.effect_mode.get(), self.effect_speed.get(), self.effect_brightness.get(), self.effect_direction.get()))
            if direction not in (1, 2):
                direction = 1
                self.effect_direction.set("1")
            if len(rgb) != 3 or any(not 0 <= c <= 255 for c in rgb) or not 1 <= mode <= 7 or not 0 <= speed <= 9 or not 0 <= brightness <= 100:
                raise ValueError
        except ValueError:
            messagebox.showerror("Keyboard lighting", "Choose a supported effect, speed from 0–9, brightness from 0–100, and RGB values from 0–255.")
            return
        if mode == 2:
            rgb = [0, 0, 0]
        firmware_direction = 3 - direction
        if write(self.backlight_dir / "four_zone_mode", ",".join(map(str, [mode, speed, brightness, firmware_direction] + rgb)), "keyboard effect"):
            active = read(self.backlight_dir / "four_zone_mode", "").split(",")
            if active and active[0].isdigit() and 0 <= int(active[0]) <= 7:
                actual_mode = int(active[0])
                self.effect_status.set(f"Firmware reports: {self._effect_name(actual_mode)}" if actual_mode == mode else f"Requested {self._effect_name(mode)}, firmware still reports {self._effect_name(actual_mode)}.")
            else:
                self.effect_status.set(f"{self._effect_name(mode)} command sent; firmware state could not be read back.")

    def apply_zones(self):
        colors = [v.get().strip().lstrip("#").lower() for v in self.zone_vars]
        if any(len(c) != 6 or any(ch not in "0123456789abcdef" for ch in c) for c in colors) or not self.zone_brightness.get().isdigit() or not 0 <= int(self.zone_brightness.get()) <= 100:
            messagebox.showerror("PredSenseLinux", "Choose a color for each zone and a brightness from 0 to 100.")
            return
        if write(self.backlight_dir / "per_zone_mode", ",".join(colors + [self.zone_brightness.get()]), "zone colors"):
            actual = read(self.backlight_dir / "per_zone_mode", "").split(",")
            requested = colors + [self.zone_brightness.get()]
            if len(actual) >= 5:
                actual = [part.strip().lower() for part in actual[:4]] + [actual[4].strip()]
                self.zone_status.set("Four zone colors applied." if actual == requested else "Firmware readback differs from the selected zone colors.")
            else:
                self.zone_status.set("Zone colors sent; firmware state could not be read back.")
            self.lighting_status.set(self.zone_status.get())
            for index in range(4):
                self._sync_zone_display(index)

    @staticmethod
    def _effect_name(mode):
        return ("Static", "Breathing", "Neon", "Wave", "Shifting", "Zoom", "Meteor", "Twinkling")[mode]

    def refresh(self):
        self.cpu_value.set(cpu_temperature())
        self.gpu_value.set(gpu_temperature())
        if hasattr(self, "cpu_usage_value"):
            self.cpu_usage_value.set(f"CPU usage  {cpu_usage()}")
            self.gpu_usage_value.set(f"GPU usage  {gpu_usage()}")
        if hasattr(self, "system_info"):
            for key, value in self._system_snapshot().items():
                self.system_info[key].set(value)
        cpu_rpm = hwmon_read("acer", "fan1_input")
        gpu_rpm = hwmon_read("acer", "fan2_input")
        self.fan_value.set(f"CPU  {cpu_rpm} RPM     GPU  {gpu_rpm} RPM")
        if hasattr(self, "fan_rpm"):
            self.fan_rpm["CPU"].set(f"{cpu_rpm} RPM")
            self.fan_rpm["GPU"].set(f"{gpu_rpm} RPM")
        choices = read(PROFILE / "choices", "").split()
        if not choices:
            choices = read("/sys/firmware/acpi/platform_profile_choices", "").split()
        self.profile_choices = choices
        current = read(PROFILE / "profile", "unknown")
        if hasattr(self, "active_profile"):
            self.active_profile.set(current.replace("-", " ").title())
        self._profile_power_changed(self._power_source_online())
        required = ("fan_speed", "battery_limiter", "usb_charging")
        missing = [name for name in required if not (SENSE / name).exists()]
        self.notice.set("Hardware interface detected." if not missing else f"{MODEL}: some controls are unavailable. Missing: {', '.join(missing)}. Confirm the module supports this laptop.")
        self.after(1500, self.refresh)


if __name__ == "__main__":
    SenseApp().mainloop()
