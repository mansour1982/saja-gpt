import os
import sys
import csv
import json
import time
import random
import difflib
import hashlib
import subprocess
import threading
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont

# -------------------------------------------------------------------
# Auto-installation check for required packages (gTTS)
# -------------------------------------------------------------------
def install_and_import(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
    except ImportError:
        print(f"Installing missing package: {package_name}...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                package_name, "--break-system-packages"
            ])
        except Exception:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", package_name
            ])

try:
    install_and_import("gTTS", "gtts")
    from gtts import gTTS
    gTTS_available = True
except Exception as e:
    print(f"Warning: Could not load gTTS ({e})")
    gTTS_available = False


CSV_FILENAME = "Saja_spelling.csv"
STAR_FILENAME = "Saja_sterwoorden.json"
# Default speaking speed: "Normaal" on the turtle/rabbit slider.
PLAYBACK_RATE = 1.0
CHOSEN_VOICE = "Xander"
STARRED_LABEL = "Sterwoorden"
STARRED_CAT_PREFIX = "\u2b50 Sterwoorden: "
UNKNOWN_CAT = "Overige"
ALL_MIX_LABEL = "\U0001f30d Alle categorie\u00ebn door elkaar"

# Starred words are Saja's progress, so there must be exactly one copy of them.
# The app can be started either through the shortcut on the Desktop or straight
# from the repository, and both routes have to reach the same file: an existing
# one always wins, and only when none exists do we create it next to the script.
_APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _first_existing(filename, fallback_dir=None):
    """Return the first of our known locations that already holds `filename`."""
    candidates = [
        os.path.join(_APP_DIR, filename),
        os.path.join(os.path.expanduser("~/Desktop"), filename),
        os.path.join(os.getcwd(), filename),
    ]
    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if os.path.exists(path):
            return path
    return os.path.join(fallback_dir or _APP_DIR, filename)


STAR_PATH = _first_existing(STAR_FILENAME)

# The word list is looked up the same way, so the app also works when it is
# double-clicked from Finder, where the working directory is not the folder
# holding the script.
def find_word_list():
    """Return the path to the word list, or None when it cannot be found."""
    path = _first_existing(CSV_FILENAME)
    return path if os.path.exists(path) else None


CSV_PATH = os.path.join(_APP_DIR, CSV_FILENAME)

# Optional Dutch -> English glosses, shown as a hint after an answer is checked.
TRANSLATION_FILENAME = "Saja_vertalingen.json"
TRANSLATION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                TRANSLATION_FILENAME)
TRANSLATION_AR_FILENAME = "Saja_vertalingen_ar.json"
TRANSLATION_AR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   TRANSLATION_AR_FILENAME)

# -------------------------------------------------------------------
# Kid-friendly look & feel
# -------------------------------------------------------------------
BG        = "#eaf4ff"   # soft sky blue page background
CARD      = "#ffffff"
INK       = "#22405e"
MUTED     = "#6b8299"
GREEN     = "#2fa360"
GREEN_LT  = "#d9f5e6"
RED       = "#e8505b"
RED_LT    = "#ffe1e3"
BLUE      = "#3d8bfd"
BLUE_LT   = "#dceaff"
YELLOW    = "#f6b93b"
YELLOW_LT = "#fff4d8"
PURPLE    = "#8e7cf3"
PURPLE_LT = "#e9e4ff"

COMPLIMENTS = [
    "Top gedaan!", "Knap hoor!", "Goed bezig!", "Helemaal goed!",
    "Wat een kanjer!", "Super!", "Yes, gelukt!", "Prima werk!",
]


def pick_font(candidates, fallback="Helvetica"):
    """Return the first installed font family from candidates."""
    try:
        available = set(tkfont.families())
    except Exception:
        return fallback
    for name in candidates:
        if name in available:
            return name
    return fallback


def shade(hex_color, factor):
    """Lighten (factor > 0) or darken (factor < 0) a #rrggbb colour."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    if factor >= 0:
        r, g, b = (int(c + (255 - c) * factor) for c in (r, g, b))
    else:
        r, g, b = (int(c * (1 + factor)) for c in (r, g, b))
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"


def round_rect_points(x1, y1, x2, y2, r):
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


class FunButton(tk.Canvas):
    """Big rounded, genuinely colourful button.

    macOS ignores `bg` on native tk.Button widgets, so the buttons are drawn
    on a Canvas instead. That keeps the playful colours on every platform.
    """

    def __init__(self, parent, text, command=None, bg=BLUE, fg="white",
                 font=None, height=58, radius=20, parent_bg=BG, wraplength=0):
        super().__init__(parent, height=height, bd=0, highlightthickness=0,
                         bg=parent_bg, takefocus=0)
        self.command = command
        self.base_bg = bg
        self.fg = fg
        self.btn_font = font
        self.radius = radius
        self.text = text
        self.wraplength = wraplength
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._shape = None
        self._shadow = None
        self._label = None
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _current_bg(self):
        if not self._enabled:
            return shade(self.base_bg, 0.55)
        if self._pressed:
            return shade(self.base_bg, -0.18)
        if self._hover:
            return shade(self.base_bg, 0.12)
        return self.base_bg

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return
        r = min(self.radius, h // 2 - 1, w // 2 - 1)
        r = max(r, 2)
        drop = 0 if self._pressed else 4
        # soft drop shadow so the button looks tactile
        self._shadow = self.create_polygon(
            round_rect_points(3, 3 + drop, w - 3, h - 3 + (0 if drop else -2), r),
            smooth=True, fill=shade(self.base_bg, -0.45), outline="")
        self._shape = self.create_polygon(
            round_rect_points(3, 3 - (0 if drop else -2), w - 3, h - 5, r),
            smooth=True, fill=self._current_bg(), outline="")
        self._label = self.create_text(
            w // 2, (h - 2) // 2, text=self.text, fill=self.fg,
            font=self.btn_font, justify="center",
            width=self.wraplength if self.wraplength else w - 20)

    def _refresh(self):
        self._draw()

    def _on_enter(self, _e=None):
        self._hover = True
        if self._enabled:
            self.config(cursor="pointinghand")
        self._refresh()

    def _on_leave(self, _e=None):
        self._hover = False
        self._pressed = False
        self._refresh()

    def _on_press(self, _e=None):
        if not self._enabled:
            return
        self._pressed = True
        self._refresh()

    def _on_release(self, _e=None):
        if not self._enabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._refresh()
        if was_pressed and self.command:
            self.command()

    def configure_button(self, text=None, bg=None, fg=None, command=None, enabled=None):
        if text is not None:
            self.text = text
        if bg is not None:
            self.base_bg = bg
        if fg is not None:
            self.fg = fg
        if command is not None:
            self.command = command
        if enabled is not None:
            self._enabled = enabled
        self._refresh()


class ProgressBar(tk.Canvas):
    """Chunky rounded progress bar with a friendly runner emoji."""

    def __init__(self, parent, height=26, parent_bg=BG, fill=GREEN, track=BLUE_LT):
        super().__init__(parent, height=height, bd=0, highlightthickness=0,
                         bg=parent_bg, takefocus=0)
        self.fill_color = fill
        self.track_color = track
        self.value = 0.0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, fraction):
        self.value = max(0.0, min(1.0, fraction))
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return
        r = h // 2
        self.create_polygon(round_rect_points(1, 1, w - 1, h - 1, r),
                            smooth=True, fill=self.track_color, outline="")
        filled = (w - 2) * self.value
        if filled > 3:
            end = max(1 + 2 * r, filled)
            self.create_polygon(round_rect_points(1, 1, min(end, w - 1), h - 1, r),
                                smooth=True, fill=self.fill_color, outline="")


def load_spelling_categories():
    path = find_word_list()
    if not path:
        return None
    try:
        with open(path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            raw_headers = next(reader)
            header_map = {}
            clean_headers = []
            seen = set()
            for idx, h in enumerate(raw_headers):
                clean_h = h.strip()
                if clean_h and clean_h not in seen:
                    seen.add(clean_h)
                    header_map[idx] = clean_h
                    clean_headers.append(clean_h)

            categories = {h: [] for h in clean_headers}
            for row in reader:
                for idx, val in enumerate(row):
                    if idx in header_map:
                        col_name = header_map[idx]
                        word = val.strip().lower()
                        if word and word not in ['-', '']:
                            categories[col_name].append(word)

            for key in categories:
                categories[key] = sorted(list(set(categories[key])))

            return clean_headers, categories
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return None


def load_starred_words():
    """Read starred words saved by a previous session. Never fatal."""
    try:
        with open(STAR_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return set()
    except Exception as e:
        print(f"Could not read starred words ({e}); starting with an empty list.")
        return set()

    # Accept either a bare list or {"starred_words": [...]}.
    if isinstance(data, dict):
        data = data.get("starred_words", [])
    if not isinstance(data, list):
        return set()
    return {str(w).strip().lower() for w in data if str(w).strip()}


def load_translations(path=None):
    """Read a Dutch -> foreign gloss file. Optional; never fatal."""
    path = path or TRANSLATION_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Could not read translations ({e}); hints will be hidden.")
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).strip().lower(): str(v).strip()
            for k, v in data.items() if str(v).strip()}


def save_starred_words(words):
    """Persist starred words. Written atomically so a crash can't corrupt it."""
    try:
        payload = {"starred_words": sorted(words)}
        tmp = STAR_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STAR_PATH)
        return True
    except Exception as e:
        print(f"Could not save starred words: {e}")
        return False


SPEECH_CACHE_DIR = os.path.join(tempfile.gettempdir(), "dictee_tts_cache")
GTTS_TIMEOUT = 2.5        # seconds to wait for the download before using 'say'
GTTS_COOLDOWN = 30.0      # after repeated failures, skip the network for a while

_speech_state = {
    "token": 0,           # newest request wins
    "proc": None,         # currently playing afplay/say process
    "fails": 0,
    "blocked_until": 0.0,
}
_speech_lock = threading.Lock()
_fetching = {}            # word -> Thread, so we never download the same word twice


def resolve_dutch_voice(preferred=CHOSEN_VOICE):
    """Fall back to any installed Dutch voice if the preferred one is missing."""
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True,
                             timeout=5).stdout
    except Exception:
        return preferred
    dutch = [ln.split()[0] for ln in out.splitlines() if "nl_NL" in ln]
    if preferred in dutch:
        return preferred
    return dutch[0] if dutch else None


def _cache_path(text):
    key = hashlib.md5(text.encode("utf-8")).hexdigest()
    return os.path.join(SPEECH_CACHE_DIR, f"{key}.mp3")


def _download_mp3(text):
    """Fetch one word to the cache. Safe to call from several threads."""
    path = _cache_path(text)
    if os.path.exists(path):
        return path
    os.makedirs(SPEECH_CACHE_DIR, exist_ok=True)
    tts = gTTS(text=text, lang="nl", slow=False)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.part"
    try:
        tts.save(tmp)
        os.replace(tmp, path)          # atomic: readers never see a partial file
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


def prefetch_speech(words):
    """Warm the cache in the background so playback is instant later."""
    if not gTTS_available:
        return
    for w in words:
        if not w or os.path.exists(_cache_path(w)):
            continue
        with _speech_lock:
            if w in _fetching:
                continue
            t = threading.Thread(target=_prefetch_one, args=(w,), daemon=True)
            _fetching[w] = t
        t.start()


def _prefetch_one(word):
    try:
        _download_mp3(word)
    except Exception:
        pass
    finally:
        with _speech_lock:
            _fetching.pop(word, None)


def stop_speech():
    """Silence whatever is playing right now."""
    with _speech_lock:
        _speech_state["token"] += 1
        proc = _speech_state["proc"]
        _speech_state["proc"] = None
    if proc and proc.poll() is None:
        try:
            proc.terminate()
        except Exception:
            pass


def speak_async(text, rate, voice):
    text = (text or "").strip()
    if not text:
        return

    # Newer requests cancel older ones, so rapid clicking can't stack up
    # overlapping voices.
    with _speech_lock:
        _speech_state["token"] += 1
        my_token = _speech_state["token"]
        old_proc = _speech_state["proc"]
        _speech_state["proc"] = None
    if old_proc and old_proc.poll() is None:
        try:
            old_proc.terminate()
        except Exception:
            pass

    def current():
        with _speech_lock:
            return _speech_state["token"] == my_token

    def play(cmd):
        if not current():
            return False
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except Exception:
            return False
        with _speech_lock:
            if _speech_state["token"] != my_token:
                proc.terminate()
                return False
            _speech_state["proc"] = proc
        proc.wait()
        with _speech_lock:
            if _speech_state["proc"] is proc:
                _speech_state["proc"] = None
        return True

    def say_fallback():
        if not voice:
            return play(["say", "-r", str(max(10, int(rate * 175))), text])
        return play(["say", "-v", voice, "-r", str(max(10, int(rate * 175))), text])

    def run_speak():
        path = _cache_path(text)

        if not os.path.exists(path) and gTTS_available:
            with _speech_lock:
                cooling = time.time() < _speech_state["blocked_until"]
            if not cooling:
                # Download in a helper thread so a hanging network call can
                # never block the fallback.
                worker = threading.Thread(target=_prefetch_one, args=(text,),
                                          daemon=True)
                with _speech_lock:
                    already = _fetching.get(text)
                    if already is None:
                        _fetching[text] = worker
                        start_it = True
                    else:
                        worker, start_it = already, False
                if start_it:
                    worker.start()
                worker.join(GTTS_TIMEOUT)

                with _speech_lock:
                    if os.path.exists(path):
                        _speech_state["fails"] = 0
                    else:
                        _speech_state["fails"] += 1
                        if _speech_state["fails"] >= 3:
                            # Network is clearly unhappy: stop paying the
                            # timeout on every single word for a while.
                            _speech_state["blocked_until"] = time.time() + GTTS_COOLDOWN
                            _speech_state["fails"] = 0

        if os.path.exists(path) and os.path.getsize(path) > 0:
            if play(["afplay", "-r", f"{rate:.2f}", path]):
                return
            if not current():
                return

        say_fallback()

    threading.Thread(target=run_speak, daemon=True).start()


def diff_letters(typed, correct):
    """Align two words and mark each letter as matching or not."""
    matcher = difflib.SequenceMatcher(a=typed, b=correct, autojunk=False)
    typed_marks, correct_marks = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        ok = (tag == "equal")
        typed_marks.extend((ch, ok) for ch in typed[i1:i2])
        correct_marks.extend((ch, ok) for ch in correct[j1:j2])
    return typed_marks, correct_marks


class SpellingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Saja GPT - Groep 6")
        self.configure(bg=BG)
        self.minsize(720, 760)

        self.init_ok = False

        data = load_spelling_categories()
        if not data:
            self.withdraw()
            messagebox.showerror(
                "File not found",
                f"Could not find '{CSV_FILENAME}'.\n\n"
                "The app looked in:\n"
                f"  \u2022 {_APP_DIR}\n"
                f"  \u2022 {os.getcwd()}\n"
                f"  \u2022 {os.path.expanduser('~/Desktop')}\n\n"
                "Put the word list in one of those folders and start again."
            )
            self.destroy()
            return

        self.headers, self.categories = data

        # Reverse index so a starred word can be traced back to its category
        # (a word may legitimately appear in more than one).
        self.word_categories = {}
        for cat in self.headers:
            for w in self.categories.get(cat, []):
                self.word_categories.setdefault(w, []).append(cat)

        self.setup_fonts()
        self.setup_styles()
        self.center_window(860, 900)

        self.selected_category = tk.StringVar(value=self.headers[0] if self.headers else "")
        self.word_count_opt = tk.StringVar(value="ALL")
        self.speed_val = tk.DoubleVar(value=PLAYBACK_RATE)
        self.track_progress_var = tk.BooleanVar(value=True)

        self.starred_words = load_starred_words()
        self.translations = load_translations()
        self.translations_ar = load_translations(TRANSLATION_AR_PATH)
        self.session_words = []
        self.current_index = 0
        self.original_total_count = 0
        self.total_attempts = 0
        self.awaiting_next = False
        self.current_word_str = ""
        self.speech_token = 0
        self.session_label = self.selected_category.get()

        self.init_ok = True
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_welcome_screen()

    def on_close(self):
        stop_speech()
        self.persist_stars()
        self.destroy()

    # ---------------------------------------------------------------
    # Look & feel helpers
    # ---------------------------------------------------------------
    def setup_fonts(self):
        fun = pick_font(["Chalkboard SE", "Comic Sans MS", "Marker Felt", "Verdana"])
        ui = pick_font(["Avenir Next", "Helvetica Neue", "Helvetica"])
        self.F_TITLE = (fun, 30, "bold")
        self.F_SUB = (ui, 15)
        self.F_CARD_TITLE = (fun, 17, "bold")
        self.F_BTN = (fun, 19, "bold")
        self.F_BTN_SM = (fun, 14, "bold")
        self.F_BODY = (ui, 14)
        self.F_BODY_B = (ui, 14, "bold")
        self.F_SMALL = (ui, 12)
        self.F_WORD = (fun, 34, "bold")
        self.F_ENTRY = (fun, 32, "bold")
        self.F_HUGE = (fun, 44, "bold")
        # Arabic needs a font that actually carries Arabic glyphs, and a
        # slightly larger size because the script has finer detail.
        arabic = pick_font(["Geeza Pro", "Al Bayan", "Damascus",
                            "Arial Unicode MS", ui])
        self.F_ARABIC = (arabic, 17, "bold")

    def setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Fun.TCombobox', fieldbackground="white", background="white",
                        foreground=INK, arrowsize=20, padding=8)
        style.configure('Fun.Horizontal.TScale', background=CARD, troughcolor=BLUE_LT)

    def center_window(self, w, h):
        """Open large: scale to the display, but keep sane bounds."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = max(w, min(int(sw * 0.62), 1280))
        h = max(h, min(int(sh * 0.88), 1200))
        w = min(w, sw - 60)
        h = min(h, sh - 90)
        x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(700, 620)

    def card(self, parent, bg=CARD, border=BLUE_LT):
        """A soft panel that groups related controls."""
        outer = tk.Frame(parent, bg=border, bd=0)
        inner = tk.Frame(outer, bg=bg, bd=0)
        inner.pack(fill="both", expand=True, padx=2, pady=2)
        return outer, inner

    def clear_screen(self):
        # A word being spoken belongs to the screen we are leaving.
        stop_speech()
        self.speech_token = getattr(self, "speech_token", 0) + 1
        # Drop global key bindings first; leftover handlers would fire on
        # widgets that are about to be destroyed.
        self.unbind_all("<Return>")
        self.unbind_all("<KP_Enter>")
        for widget in self.winfo_children():
            widget.destroy()

    def all_words(self):
        """Every unique word across all categories."""
        combined = set()
        for words in self.categories.values():
            combined.update(words)
        return sorted(combined)

    def starred_by_category(self):
        """Group the starred words by the category they came from."""
        groups = {}
        for w in self.starred_words:
            for cat in self.word_categories.get(w, [UNKNOWN_CAT]):
                groups.setdefault(cat, []).append(w)
        ordered = {}
        for cat in self.headers + [UNKNOWN_CAT]:
            if cat in groups:
                ordered[cat] = sorted(groups[cat])
        return ordered

    def words_for_category(self, cat):
        """Resolve a combobox label to its word list."""
        if cat.startswith(ALL_MIX_LABEL):
            return self.all_words()
        return list(self.categories.get(cat, []))

    def starred_for_category(self, cat=None):
        """The starred words that belong to the chosen category."""
        cat = self.selected_category.get() if cat is None else cat
        pool = set(self.words_for_category(cat))
        return sorted(w for w in self.starred_words if w in pool)

    def get_category_options(self):
        options = list(self.headers)
        options.insert(0, f"{ALL_MIX_LABEL} ({len(self.all_words())})")
        return options

    # ---------------------------------------------------------------
    # Welcome screen
    # ---------------------------------------------------------------
    def show_welcome_screen(self):
        self.clear_screen()

        page = tk.Frame(self, bg=BG)
        page.pack(fill="both", expand=True, padx=26, pady=18)

        # --- Title banner -------------------------------------------
        banner_out, banner = self.card(page, bg=YELLOW_LT, border=YELLOW)
        banner_out.pack(fill="x")
        tk.Label(banner, text="\u270f\ufe0f  SAJA GPT  \U0001f4da", font=self.F_TITLE,
                 bg=YELLOW_LT, fg="#8a5a00").pack(pady=(12, 0))
        tk.Label(banner, text="Groep 6  \u00b7  luister goed en type het woord!",
                 font=self.F_SUB, bg=YELLOW_LT, fg="#8a5a00").pack(pady=(2, 12))

        # Pack the two action buttons from the bottom *before* the cards so
        # `pack` always reserves room for them; otherwise a short window
        # silently drops the START button off the layout entirely.
        self.start_btn = FunButton(page, text="\U0001f680   START!", font=(self.F_BTN[0], 24, "bold"),
                                   bg=GREEN, height=74, radius=24, parent_bg=BG,
                                   command=self.start_quiz)
        self.start_btn.pack(fill="x", side="bottom", pady=(14, 4))

        self.repeat_btn = FunButton(page, text="", font=self.F_BTN_SM, height=52,
                                    radius=18, parent_bg=BG, command=self.toggle_repeat_mode)
        self.repeat_btn.pack(fill="x", side="bottom")
        self.refresh_repeat_button()

        # Middle area holds the three setup cards and absorbs any leftover space.
        middle = tk.Frame(page, bg=BG)
        middle.pack(fill="both", expand=True)

        # --- 1. Category --------------------------------------------
        cat_out, cat = self.card(middle)
        cat_out.pack(fill="x", pady=(14, 0))
        tk.Label(cat, text="1\ufe0f\u20e3   Welke woorden ga je oefenen?", font=self.F_CARD_TITLE,
                 bg=CARD, fg=INK).pack(anchor="w", padx=16, pady=(10, 6))

        cat_options = self.get_category_options()
        if self.selected_category.get() not in cat_options:
            self.selected_category.set(cat_options[0])

        self.category_menu = ttk.Combobox(
            cat, textvariable=self.selected_category, values=cat_options,
            state="readonly", font=(self.F_BODY[0], 15), style='Fun.TCombobox')
        self.category_menu.pack(fill="x", padx=16, pady=(0, 8))

        self.cat_count_lbl = tk.Label(cat, text="", font=self.F_SMALL, bg=CARD, fg=MUTED)
        self.cat_count_lbl.pack(anchor="w", padx=18, pady=(0, 4))
        self.star_note = tk.Label(cat, text="", font=self.F_SMALL, bg=CARD, fg="#6b4700",
                                  justify="left")
        if self.starred_words:
            self.star_note.config(
                text=f"\u2b50  {len(self.starred_words)} sterwoorden bewaard \u2014 kies hieronder "
                     f"\u201c\u2b50 Sterwoorden\u201d om ze per categorie te oefenen.")
        self.star_note.pack(anchor="w", padx=18, pady=(0, 12))
        self.category_menu.bind("<<ComboboxSelected>>", lambda e: self.update_word_total())
        self.update_word_total()

        # --- 2. How many words --------------------------------------
        cnt_out, cnt = self.card(middle)
        cnt_out.pack(fill="x", pady=(12, 0))
        tk.Label(cnt, text="2\ufe0f\u20e3   Welke woorden?", font=self.F_CARD_TITLE,
                 bg=CARD, fg=INK).pack(anchor="w", padx=16, pady=(10, 6))

        row = tk.Frame(cnt, bg=CARD)
        row.pack(fill="x", padx=16, pady=(0, 12))
        self.count_buttons = {}
        for col, (val, label) in enumerate([("ALL", "Alle\nwoorden"),
                                            ("STAR", "\u2b50 Ster-\nwoorden")]):
            btn = FunButton(row, text=label, font=self.F_BTN_SM, height=66, radius=18,
                            parent_bg=CARD, command=lambda v=val: self.set_word_count(v))
            # grid (not pack) so narrow windows shrink the buttons instead of
            # dropping one of them entirely.
            btn.configure(width=52)
            btn.grid(row=0, column=col, sticky="ew", padx=4)
            row.grid_columnconfigure(col, weight=1, uniform="cnt")
            self.count_buttons[val] = btn
        self.count_hint = tk.Label(cnt, text="", font=self.F_BODY, bg=CARD, fg=MUTED)
        self.count_hint.pack(anchor="w", padx=18, pady=(0, 12))
        self.refresh_count_buttons()
        self.update_word_total()

        # --- 3. Voice speed -----------------------------------------
        spd_out, spd = self.card(middle)
        spd_out.pack(fill="x", pady=(12, 0))
        tk.Label(spd, text="3\ufe0f\u20e3   Hoe snel praat de stem?", font=self.F_CARD_TITLE,
                 bg=CARD, fg=INK).pack(anchor="w", padx=16, pady=(10, 2))

        srow = tk.Frame(spd, bg=CARD)
        srow.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(srow, text="\U0001f422", font=(self.F_BODY[0], 22), bg=CARD).pack(side="left")
        slider = ttk.Scale(srow, from_=0.3, to=1.2, orient="horizontal",
                           variable=self.speed_val, style='Fun.Horizontal.TScale',
                           command=lambda v: self.update_speed_label())
        slider.pack(side="left", fill="x", expand=True, padx=10)
        tk.Label(srow, text="\U0001f407", font=(self.F_BODY[0], 22), bg=CARD).pack(side="left")

        brow = tk.Frame(spd, bg=CARD)
        brow.pack(fill="x", padx=16, pady=(0, 12))
        self.speed_lbl = tk.Label(brow, text="", font=self.F_BODY_B, bg=CARD, fg=BLUE)
        self.speed_lbl.pack(side="left")
        FunButton(brow, text="\U0001f50a  Probeer de stem", font=self.F_BTN_SM, bg=PURPLE,
                  height=46, radius=16, parent_bg=CARD,
                  command=lambda: speak_async("hallo, dit is de stem", self.speed_val.get(), CHOSEN_VOICE)
                  ).pack(side="right", ipadx=6)
        self.update_speed_label()

    def update_word_total(self):
        # Only meaningful while the welcome screen is alive.
        lbl = getattr(self, "cat_count_lbl", None)
        if lbl is None or not lbl.winfo_exists():
            return
        total = len(self.words_for_category(self.selected_category.get()))
        stars = len(self.starred_for_category())
        lbl.config(text=f"\U0001f4d6  {total} woorden in deze lijst"
                        f"      \u2b50 {stars} sterwoorden")

        # Keep the "all words" / star buttons and the hint line in sync.
        buttons = getattr(self, "count_buttons", {})
        btn = buttons.get("ALL")
        if btn is not None and btn.winfo_exists():
            btn.configure_button(text=f"Alle {total}\nwoorden")
        sbtn = buttons.get("STAR")
        if sbtn is not None and sbtn.winfo_exists():
            sbtn.configure_button(text=f"\u2b50 {stars}\nsterwoorden", enabled=stars > 0)
        if self.word_count_opt.get() == "STAR" and stars == 0:
            self.word_count_opt.set("ALL")
        self.refresh_count_buttons()
        self.update_count_hint()

    def update_count_hint(self):
        hint = getattr(self, "count_hint", None)
        if hint is None or not hint.winfo_exists():
            return
        total = len(self.words_for_category(self.selected_category.get()))
        choice = self.word_count_opt.get()
        if choice == "STAR":
            stars = len(self.starred_for_category())
            hint.config(text=f"\u2b50  Je oefent de {stars} sterwoorden van deze categorie.")
        else:
            hint.config(text=f"\u2705  Je oefent alle {total} woorden van deze lijst.")

    def set_word_count(self, value):
        if value == "STAR" and not self.starred_for_category():
            return
        self.word_count_opt.set(value)
        self.refresh_count_buttons()
        self.update_count_hint()

    def refresh_count_buttons(self):
        chosen = self.word_count_opt.get()
        for val, btn in list(getattr(self, "count_buttons", {}).items()):
            # The welcome screen may already have been torn down.
            if not btn.winfo_exists():
                continue
            if val == "STAR" and not self.starred_for_category():
                btn.configure_button(bg="#f0f0f0", fg="#b9b9b9", enabled=False)
            elif val == chosen:
                btn.configure_button(bg=YELLOW if val == "STAR" else BLUE,
                                     fg="#5a3d00" if val == "STAR" else "white",
                                     enabled=True)
            else:
                btn.configure_button(bg="#e6eef7", fg=MUTED, enabled=True)

    def toggle_repeat_mode(self):
        self.track_progress_var.set(not self.track_progress_var.get())
        self.refresh_repeat_button()

    def refresh_repeat_button(self):
        if not hasattr(self, "repeat_btn") or not self.repeat_btn.winfo_exists():
            return
        if self.track_progress_var.get():
            self.repeat_btn.configure_button(
                text="\U0001f501   Foute woorden komen terug:  AAN", bg=GREEN, fg="white")
        else:
            self.repeat_btn.configure_button(
                text="\u27a1\ufe0f   Foute woorden komen terug:  UIT", bg="#e6eef7", fg=MUTED)

    def update_speed_label(self):
        v = self.speed_val.get()
        if v <= 0.5:
            txt = "\U0001f422  Heel langzaam"
        elif v <= 0.75:
            txt = "\U0001f6b6  Rustig"
        elif v <= 1.0:
            txt = "\U0001f642  Normaal"
        else:
            txt = "\U0001f407  Snel"
        if hasattr(self, "speed_lbl") and self.speed_lbl.winfo_exists():
            self.speed_lbl.config(text=txt)

    # ---------------------------------------------------------------
    # Quiz flow
    # ---------------------------------------------------------------
    def start_quiz(self, custom_words=None):
        star_mode = False
        if custom_words is not None:
            word_pool = list(custom_words)
            self.session_label = STARRED_LABEL
        else:
            cat = self.selected_category.get()
            base_label = "Alle categorie\u00ebn" if cat.startswith(ALL_MIX_LABEL) else cat
            star_mode = self.word_count_opt.get() == "STAR"
            if star_mode:
                word_pool = self.starred_for_category(cat)
                self.session_label = f"\u2b50 {base_label}"
            else:
                word_pool = self.words_for_category(cat)
                self.session_label = base_label

        if not word_pool:
            if star_mode:
                messagebox.showinfo(
                    "Nog geen sterwoorden",
                    "In deze categorie staan nog geen sterwoorden.\n\n"
                    "Woorden krijgen vanzelf een \u2b50 als ze fout gaan, "
                    "of je kunt ze zelf een ster geven tijdens het oefenen.")
            else:
                messagebox.showwarning(
                    "No words available",
                    "There are no words to practise in this category.\n\n"
                    "Check that the word list is complete.")
            return

        random.shuffle(word_pool)
        selected_words = word_pool

        # A stable list: words are never removed, so you can navigate back to
        # any of them regardless of whether they were answered.
        self.session_words = [{"word": w, "attempts": 0, "status": "new",
                               "typed": "", "first_try": False}
                              for w in selected_words]
        self.current_index = 0
        self.original_total_count = len(self.session_words)
        self.total_attempts = 0

        # Warm the first words so the very first prompt is instant.
        prefetch_speech([it["word"] for it in self.session_words[:6]])

        self.show_practice_screen()

    # --- session helpers ------------------------------------------------
    @property
    def current_item(self):
        if 0 <= self.current_index < len(self.session_words):
            return self.session_words[self.current_index]
        return None

    @property
    def first_try_correct(self):
        return sum(1 for it in self.session_words if it.get("first_try"))

    def answered_count(self):
        return sum(1 for it in self.session_words if it["status"] != "new")

    def correct_count(self):
        return sum(1 for it in self.session_words if it["status"] == "correct")

    def unfinished_indexes(self):
        """Words still needing work, in order, starting after the current one."""
        if self.track_progress_var.get():
            bad = lambda it: it["status"] != "correct"
        else:
            bad = lambda it: it["status"] == "new"
        n = len(self.session_words)
        if n == 0:
            return []
        order = [(self.current_index + 1 + i) % n for i in range(n)]
        return [i for i in order if bad(self.session_words[i])]

    def session_finished(self):
        return not self.unfinished_indexes() and self.answered_count() > 0

    def show_practice_screen(self):
        self.clear_screen()
        self.awaiting_next = False
        item = self.current_item
        self.current_word_str = item["word"] if item else ""

        page = tk.Frame(self, bg=BG)
        page.pack(fill="both", expand=True, padx=26, pady=18)

        # --- Header: category chip + score --------------------------
        head = tk.Frame(page, bg=BG)
        head.pack(fill="x")

        chip = tk.Label(head, text=f"  \U0001f4d6  {self.session_label}  ", font=self.F_SMALL,
                        bg=PURPLE_LT, fg="#4b3fa8", padx=6, pady=6)
        chip.pack(side="left")

        self.score_lbl = tk.Label(
            head, text=self.score_text(), font=self.F_BODY_B, bg=BG, fg=GREEN)
        self.score_lbl.pack(side="right")

        # --- Progress ------------------------------------------------
        total = self.original_total_count
        done = self.correct_count()
        prog_text = (f"Woord {self.current_index + 1} van de {total}"
                     f"      \u2714\ufe0f {done} goed")

        self.progress = ProgressBar(page, parent_bg=BG)
        self.progress.pack(fill="x", pady=(14, 4))
        self.progress.set(done / total if total else 0)

        tk.Label(page, text=prog_text, font=self.F_SMALL, bg=BG, fg=MUTED).pack(anchor="w")

        # --- Bottom buttons (packed early so they are never dropped) --
        btn_row = tk.Frame(page, bg=BG)
        btn_row.pack(fill="x", side="bottom", pady=(10, 0))

        stop_btn = FunButton(btn_row, text="\u2b05\ufe0f  Stop", font=self.F_BTN_SM, bg="#e6eef7",
                             fg=MUTED, height=56, radius=18, parent_bg=BG,
                             command=self.show_welcome_screen)

        self.star_btn = FunButton(btn_row, text="", font=self.F_BTN_SM, height=56,
                                  radius=18, parent_bg=BG,
                                  command=self.toggle_star_current_word)

        self.action_btn = FunButton(btn_row, text="\u2705  Nakijken", font=self.F_BTN,
                                    bg=GREEN, height=56, radius=18, parent_bg=BG,
                                    command=self.check_answer)

        # grid, not pack: a narrow window shrinks these instead of silently
        # dropping whichever one no longer fits.
        for col, (b, weight) in enumerate(((stop_btn, 1), (self.star_btn, 2),
                                           (self.action_btn, 2))):
            b.configure(width=60)
            b.grid(row=0, column=col, sticky="ew", padx=4)
            btn_row.grid_columnconfigure(col, weight=weight)

        # --- Word navigation (skip / go back) -------------------------
        nav_row = tk.Frame(page, bg=BG)
        nav_row.pack(fill="x", side="bottom", pady=(8, 0))
        # grid, not pack: narrow windows shrink these instead of dropping one.
        self.back_btn = FunButton(nav_row, text="\u23ee\ufe0f  Vorig woord", font=self.F_BTN_SM,
                                  height=50, radius=16, parent_bg=BG, command=self.previous_word)
        self.skip_btn = FunButton(nav_row, text="Sla over  \u23ed\ufe0f", font=self.F_BTN_SM,
                                  height=50, radius=16, parent_bg=BG, command=self.skip_word)
        for col, b in enumerate((self.back_btn, self.skip_btn)):
            b.configure(width=60)
            b.grid(row=0, column=col, sticky="ew", padx=4)
            nav_row.grid_columnconfigure(col, weight=1, uniform="nav")
        self.refresh_nav_buttons()

        # --- Listen --------------------------------------------------
        FunButton(page, text="\U0001f50a   LUISTER NOG EEN KEER", font=(self.F_BTN[0], 21, "bold"),
                  bg=BLUE, height=96, radius=26, parent_bg=BG,
                  command=self.speak_current_word).pack(fill="x", pady=(16, 6))
        tk.Label(page, text="Tip: druk op Enter bij een leeg vakje om het woord opnieuw te horen",
                 font=self.F_SMALL, bg=BG, fg=MUTED).pack()

        # --- Voice speed (same setting as on the home screen) ---------
        spd_row = tk.Frame(page, bg=BG)
        spd_row.pack(fill="x", pady=(8, 0))
        tk.Label(spd_row, text="\U0001f422", font=(self.F_BODY[0], 18), bg=BG).pack(side="left")
        ttk.Scale(spd_row, from_=0.3, to=1.2, orient="horizontal",
                  variable=self.speed_val, style='Fun.Horizontal.TScale',
                  command=lambda v: self.update_speed_label()
                  ).pack(side="left", fill="x", expand=True, padx=8)
        tk.Label(spd_row, text="\U0001f407", font=(self.F_BODY[0], 18), bg=BG).pack(side="left")
        self.speed_lbl = tk.Label(spd_row, text="", font=self.F_SMALL, bg=BG, fg=BLUE,
                                  width=14, anchor="w")
        self.speed_lbl.pack(side="left", padx=(10, 0))
        self.update_speed_label()

        # --- Typing --------------------------------------------------
        status = item["status"] if item else "new"
        prompt = {"new": "Typ hier het woord:",
                  "correct": "\u2714\ufe0f  Dit woord had je goed \u2014 je mag het nog eens proberen:",
                  "wrong": "\u274c  Dit woord ging fout \u2014 probeer het opnieuw:"}[status]
        tk.Label(page, text=prompt, font=self.F_CARD_TITLE,
                 bg=BG, fg=INK).pack(anchor="w", pady=(16, 6))

        border_col = {"new": BLUE_LT, "correct": GREEN, "wrong": RED}[status]
        self.entry_border = tk.Frame(page, bg=border_col)
        self.entry_border.pack(fill="x")
        self.entry_box = tk.Entry(self.entry_border, font=self.F_ENTRY, justify="center",
                                  bd=0, relief="flat", bg="white", fg=INK,
                                  insertbackground=BLUE, highlightthickness=0)
        self.entry_box.pack(fill="x", padx=4, pady=4, ipady=12)
        self.entry_box.focus_set()

        self.bind_all("<Return>", self.handle_enter_key)
        self.bind_all("<KP_Enter>", self.handle_enter_key)

        # --- Feedback area -------------------------------------------
        self.feedback_zone = tk.Frame(page, bg=BG)
        self.feedback_zone.pack(fill="both", expand=True, pady=(12, 0))

        self.update_star_button_ui()
        self.refresh_nav_buttons()
        self.refresh_action_button()

        # Cancel any pending/playing speech from the previous word, then queue
        # this one and warm up the words around it.
        stop_speech()
        self.speech_token += 1
        token = self.speech_token
        self.after(400, lambda: self.speak_current_word(token))
        nearby = self.session_words[self.current_index:self.current_index + 4]
        prefetch_speech([it["word"] for it in nearby])

    def refresh_action_button(self):
        """The main button is 'check' until answered, then 'next' / 'finish'."""
        if not hasattr(self, "action_btn") or not self.action_btn.winfo_exists():
            return
        if self.session_finished():
            self.action_btn.configure_button(text="\U0001f3c1  Bekijk je score",
                                             command=self.show_result_screen,
                                             bg=PURPLE, fg="white")
        elif self.awaiting_next:
            self.action_btn.configure_button(text="Volgende  \u27a1\ufe0f",
                                             command=self.next_word,
                                             bg=BLUE, fg="white")
        else:
            self.action_btn.configure_button(text="\u2705  Nakijken",
                                             command=self.check_answer,
                                             bg=GREEN, fg="white")

    def score_text(self):
        return f"\u2b50 In 1x goed: {self.first_try_correct}/{self.original_total_count}"

    def speak_current_word(self, token=None):
        # A timer from a screen the child has already left must stay silent.
        if token is not None and token != self.speech_token:
            return
        if self.current_word_str:
            speak_async(self.current_word_str, self.speed_val.get(), CHOSEN_VOICE)

    def handle_enter_key(self, event=None):
        if self.awaiting_next:
            self.next_word()
            return "break"

        if not self.entry_box.get().strip():
            self.speak_current_word()
        else:
            self.check_answer()

        return "break"

    def update_star_button_ui(self):
        if self.current_word_str in self.starred_words:
            self.star_btn.configure_button(text="\u2b50  Sterwoord", bg=YELLOW, fg="#6b4700")
        else:
            self.star_btn.configure_button(text="\u2606  Onthoud dit woord", bg="#e6eef7", fg=MUTED)

    def persist_stars(self):
        save_starred_words(self.starred_words)

    def toggle_star_current_word(self):
        if not self.current_word_str:
            return
        if self.current_word_str in self.starred_words:
            self.starred_words.remove(self.current_word_str)
        else:
            self.starred_words.add(self.current_word_str)
        self.persist_stars()
        self.update_star_button_ui()

    def letter_row(self, parent, label, marks, bg, ok_color, bad_color):
        row = tk.Frame(parent, bg=bg)
        row.pack(anchor="w", pady=3)
        tk.Label(row, text=label, font=self.F_BODY, bg=bg, fg=MUTED,
                 width=10, anchor="w").pack(side="left")
        for ch, ok in marks:
            tk.Label(row, text=ch, font=(self.F_WORD[0], 24, "bold"),
                     bg="white" if ok else bad_color,
                     fg=ok_color if ok else "white",
                     width=2, pady=2).pack(side="left", padx=1)
        return row

    def translation_for(self, word, table=None):
        """Best gloss for a Dutch word, or '' when we don't know one."""
        table = self.translations if table is None else table
        if not table:
            return ""
        word = (word or "").strip().lower()
        gloss = table.get(word, "")
        if gloss:
            return gloss
        # A few forgiving fallbacks so simple inflections still show a hint.
        for suffix, stem_extra in (("tje", ""), ("etje", ""), ("pje", ""),
                                   ("je", ""), ("en", ""), ("s", ""), ("e", "")):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                stem = word[: len(word) - len(suffix)] + stem_extra
                for cand in (stem, stem + "e", stem[:-1] if len(stem) > 3 else stem):
                    gloss = table.get(cand, "")
                    if gloss:
                        return gloss
        return ""

    def add_translation_hint(self, parent, word, bg):
        """Show the English and Arabic meaning; skip a line we don't know."""
        lines = (
            ("\U0001f1ec\U0001f1e7  In het Engels: ",
             self.translation_for(word, self.translations), self.F_BODY_B),
            ("\U0001f1f8\U0001f1e6  In het Arabisch: ",
             self.translation_for(word, self.translations_ar), self.F_ARABIC),
        )
        shown = [(prefix, gloss, font) for prefix, gloss, font in lines if gloss]
        if not shown:
            return
        for i, (prefix, gloss, font) in enumerate(shown):
            last = i == len(shown) - 1
            tk.Label(parent, text=f"{prefix}{gloss}", font=font, bg=bg, fg=BLUE
                     ).pack(anchor="w", padx=14, pady=(0, 12 if last else 2))

    def check_answer(self):
        user_input = self.entry_box.get().strip().lower()
        current_item = self.current_item
        if not user_input or current_item is None:
            self.speak_current_word()
            return

        correct_word = current_item["word"]

        self.entry_box.config(state="readonly")
        self.awaiting_next = True
        self.focus_force()

        self.total_attempts += 1
        current_item["attempts"] += 1
        current_item["typed"] = user_input
        # First-try credit is decided once and never changes, so practising a
        # word again can neither inflate nor destroy the score.
        if current_item["attempts"] == 1 and user_input == correct_word:
            current_item["first_try"] = True

        for child in self.feedback_zone.winfo_children():
            child.destroy()

        if user_input == correct_word:
            current_item["status"] = "correct"
            self.entry_border.config(bg=GREEN)
            box_out, box = self.card(self.feedback_zone, bg=GREEN_LT, border=GREEN)
            box_out.pack(fill="x")
            tk.Label(box, text=f"\U0001f389  {random.choice(COMPLIMENTS)}", font=self.F_HUGE,
                     bg=GREEN_LT, fg=GREEN).pack(pady=(10, 0))
            tk.Label(box, text=correct_word, font=self.F_WORD,
                     bg=GREEN_LT, fg=GREEN).pack(pady=(0, 6))
            self.add_translation_hint(box, correct_word, GREEN_LT)
        else:
            current_item["status"] = "wrong"
            self.entry_border.config(bg=RED)
            self.starred_words.add(correct_word)
            self.persist_stars()

            box_out, box = self.card(self.feedback_zone, bg=RED_LT, border=RED)
            box_out.pack(fill="x")
            tk.Label(box, text="\U0001f9d0  Bijna! Kijk goed naar de letters:",
                     font=self.F_CARD_TITLE, bg=RED_LT, fg="#a32b33").pack(anchor="w",
                                                                          padx=14, pady=(10, 6))

            typed_marks, correct_marks = diff_letters(user_input, correct_word)
            self.letter_row(box, "Jij typte:", typed_marks, RED_LT, INK, RED)
            self.letter_row(box, "Goed is:", correct_marks, RED_LT, GREEN, YELLOW)
            self.add_translation_hint(box, correct_word, RED_LT)
            tk.Label(box, text="Je komt vanzelf nog een keer bij dit woord terug \U0001f501"
                     if self.track_progress_var.get() else "Onthoud dit woord goed!",
                     font=self.F_SMALL, bg=RED_LT, fg="#a32b33").pack(anchor="w",
                                                                      padx=14, pady=(6, 12))

            speak_async(correct_word, self.speed_val.get(), CHOSEN_VOICE)

        self.update_star_button_ui()
        self.refresh_nav_buttons()
        self.refresh_action_button()
        self.score_lbl.config(text=self.score_text())

    def refresh_nav_buttons(self):
        """Grey out navigation that would not do anything right now."""
        for btn, can in ((self.back_btn, self.can_go_back()),
                         (self.skip_btn, self.can_skip())):
            if not btn.winfo_exists():
                continue
            if can:
                btn.configure_button(enabled=True, bg=PURPLE, fg="white")
            else:
                btn.configure_button(enabled=False, bg="#e6eef7", fg=MUTED)

    def can_go_back(self):
        return self.current_index > 0

    def can_skip(self):
        return self.current_index < len(self.session_words) - 1

    def skip_word(self):
        """Move one word forward, answered or not."""
        if not self.can_skip():
            return
        self.current_index += 1
        self.show_practice_screen()

    def previous_word(self):
        """Move one word back, answered or not."""
        if not self.can_go_back():
            return
        self.current_index -= 1
        self.show_practice_screen()

    def next_word(self):
        """After checking: jump to the next word that still needs work."""
        pending = self.unfinished_indexes()
        if pending:
            self.current_index = pending[0]
            self.show_practice_screen()
        else:
            self.show_result_screen()

    # ---------------------------------------------------------------
    # Result screen
    # ---------------------------------------------------------------
    def show_result_screen(self):
        self.clear_screen()

        page = tk.Frame(self, bg=BG)
        page.pack(fill="both", expand=True, padx=26, pady=18)

        score_percentage = (self.first_try_correct / self.original_total_count) * 100 \
            if self.original_total_count else 0

        if score_percentage >= 85:
            stars, compliment, tint, edge = 3, "Super! Een fantastische score!", GREEN_LT, GREEN
        elif score_percentage >= 50:
            stars, compliment, tint, edge = 2, "Hartstikke goed! Je bent goed op weg.", YELLOW_LT, YELLOW
        else:
            stars, compliment, tint, edge = 1, "Goed geoefend! Blijf zo doorgaan!", BLUE_LT, BLUE

        # Reserve the bottom button first so a short window cannot drop it.
        FunButton(page, text="\U0001f3e0  Naar het menu", font=self.F_BTN, bg=BLUE,
                  height=64, radius=20, parent_bg=BG,
                  command=self.show_welcome_screen).pack(fill="x", side="bottom", pady=(16, 4))

        top_out, top = self.card(page, bg=tint, border=edge)
        top_out.pack(fill="x")
        tk.Label(top, text="\U0001f389  KLAAR!  \U0001f389", font=self.F_TITLE,
                 bg=tint, fg=INK).pack(pady=(14, 2))
        tk.Label(top, text="\u2b50" * stars + "\u2606" * (3 - stars),
                 font=(self.F_WORD[0], 46), bg=tint, fg=YELLOW).pack(pady=2)
        tk.Label(top, text=f"In 1 keer goed: {self.first_try_correct} van de {self.original_total_count}",
                 font=(self.F_BODY[0], 17, "bold"), bg=tint, fg=INK).pack(pady=(6, 0))
        tk.Label(top, text=f"Aantal pogingen: {self.total_attempts}  \u00b7  {self.session_label}",
                 font=self.F_SMALL, bg=tint, fg=MUTED).pack()
        tk.Label(top, text=compliment, font=(self.F_BODY[0], 15, "italic"),
                 bg=tint, fg=INK).pack(pady=(8, 14))

        if self.starred_words:
            star_out, star_box = self.card(page, bg=YELLOW_LT, border=YELLOW)
            star_out.pack(fill="both", expand=True, pady=(16, 0))

            tk.Label(star_box, text=f"\u2b50  Woorden om te oefenen ({len(self.starred_words)})",
                     font=self.F_CARD_TITLE, bg=YELLOW_LT, fg="#8a5a00").pack(pady=(12, 2))
            tk.Label(star_box,
                     text="Gesorteerd per categorie \u2014 ze blijven bewaard voor de volgende keer.",
                     font=self.F_SMALL, bg=YELLOW_LT, fg=MUTED).pack(pady=(0, 6))

            list_frame = tk.Frame(star_box, bg=YELLOW_LT)
            list_frame.pack(fill="both", expand=True, padx=14)
            scroll = tk.Scrollbar(list_frame)
            scroll.pack(side="right", fill="y")
            listbox = tk.Listbox(list_frame, font=(self.F_WORD[0], 16), bg="white", fg=INK,
                                 bd=0, highlightthickness=0, selectbackground=YELLOW,
                                 height=8, yscrollcommand=scroll.set, activestyle="none")
            # Group by category so it is clear which topic still needs work.
            for cat, words in self.starred_by_category().items():
                listbox.insert(tk.END, f" {cat}  ({len(words)})")
                listbox.itemconfig(tk.END, foreground="#8a5a00",
                                   background="#fff4d6", selectbackground=YELLOW)
                for w in words:
                    listbox.insert(tk.END, f"       {w}")
            listbox.pack(side="left", fill="both", expand=True)
            scroll.config(command=listbox.yview)

            btn_row = tk.Frame(star_box, bg=YELLOW_LT)
            btn_row.pack(fill="x", padx=14, pady=12)
            FunButton(btn_row, text="\U0001f504  Oefen deze woorden", font=self.F_BTN_SM,
                      bg=GREEN, height=54, radius=18, parent_bg=YELLOW_LT,
                      command=lambda: self.start_quiz(custom_words=set(self.starred_words))
                      ).pack(side="left", expand=True, fill="x", padx=(0, 5))
            FunButton(btn_row, text="\U0001f9f9  Wis lijst", font=self.F_BTN_SM,
                      bg="#e6eef7", fg=MUTED, height=54, radius=18, parent_bg=YELLOW_LT,
                      command=self.clear_starred_words
                      ).pack(side="left", expand=True, fill="x", padx=(5, 0))

    def clear_starred_words(self):
        if not messagebox.askyesno(
                "Weet je het zeker?",
                f"Wil je alle {len(self.starred_words)} sterwoorden wissen?\n\n"
                "Deze lijst wordt bewaard, dus je kunt hem daarna niet meer terughalen."):
            return
        self.starred_words.clear()
        self.persist_stars()
        messagebox.showinfo("Gewist", "De lijst met sterwoorden is leeggemaakt.")
        self.show_result_screen()


if __name__ == "__main__":
    # Pick a voice that actually exists, so the fallback can never be silent.
    CHOSEN_VOICE = resolve_dutch_voice()
    app = SpellingApp()
    if app.init_ok:
        app.mainloop()
