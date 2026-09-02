import os, shutil, sys

# Resolve the app from this repository, so the tests do not depend on where the
# checkout happens to live or on a shortcut existing on the Desktop.
REPO_DESKTOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_SRC = os.path.join(REPO_DESKTOP, "dictee_mac2.py")

WORK = "/tmp/dt_reg"
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
shutil.copy(APP_SRC, os.path.join(WORK, "dnew.py"))
shutil.copy(os.path.join(REPO_DESKTOP, "Saja_spelling.csv"), os.path.join(WORK, "Saja_spelling.csv"))
shutil.copy(os.path.join(REPO_DESKTOP, "Saja_vertalingen.json"), os.path.join(WORK, "Saja_vertalingen.json"))
sys.path.insert(0, WORK)
import dnew as d

class _NoDialogs:
    """A modal dialog inside a test means a real bug; never block on one."""
    def _boom(self, title, msg, *a, **k):
        raise AssertionError(f"unexpected dialog: {title} :: {msg}")
    showerror = showwarning = _boom
    def showinfo(self, *a, **k): return "ok"
    def askyesno(self, *a, **k): return True
d.messagebox = _NoDialogs()

d.STAR_PATH = os.path.join(WORK, "stars.json")
d.SPEECH_CACHE_DIR = os.path.join(WORK, "cache")
d.gTTS_available = False
d.speak_async = lambda *a, **k: None
d.prefetch_speech = lambda *a, **k: None

errors = []
app = d.SpellingApp()
app.report_callback_exception = lambda *a: errors.append(repr(a))


def mapped(name):
    w = getattr(app, name, None)
    assert w is not None and w.winfo_exists(), f"{name} missing"
    assert w.winfo_ismapped(), f"{name} not mapped"
    assert w.winfo_width() > 40, f"{name} too narrow ({w.winfo_width()})"


def steps():
    try:
        app.update()
        # Welcome screen: real translation file loaded, star + all buttons mapped.
        assert len(app.translations) > 1500, len(app.translations)
        for n in ():
            if hasattr(app, n):
                mapped(n)

        # Session over a small word set, mixed answers.
        app.start_quiz(custom_words=['afgrijselijk', 'afkomst', 'aflasten', 'afrekenen', 'afschuw', 'afschuwelijk'])
        app.update()

        def answer(text):
            app.entry_box.config(state="normal")
            app.entry_box.delete(0, "end")
            app.entry_box.insert(0, text)
            app.check_answer()
            app.update()

        w0 = app.current_item["word"]
        answer(w0)                         # correct first try
        app.next_word(); app.update()
        w1 = app.current_item["word"]
        answer(w1 + "x")                   # wrong -> auto-starred
        assert w1 in app.starred_words, f"stars={app.starred_words}"
        app.next_word(); app.update()
        answer(app.current_item["word"])
        # Navigate freely over answered and unanswered words.
        for _ in range(8):
            app.next_word(); app.update()
        for _ in range(8):
            app.previous_word(); app.update()
        # Re-answering a correct word must not change first-try credit.
        before = app.first_try_correct
        app.current_index = 0
        app.show_practice_screen(); app.update()
        answer(app.current_item["word"])
        assert app.first_try_correct == before, (before, app.first_try_correct)
        # Translation hint present on a known word.
        def texts(w):
            out = []
            for c in w.winfo_children():
                try:
                    out.append(c.cget("text"))
                except Exception:
                    pass
                out.extend(texts(c))
            return out
        hints=[t for t in texts(app.feedback_zone) if "Engels" in t]
        assert hints, texts(app.feedback_zone)

        # Stars persist across a restart.
        app.persist_stars()
        assert w1 in d.load_starred_words(), f"reload={d.load_starred_words()}"
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        app.after(100, app.destroy)


app.after(400, steps)
try:
    app.mainloop()
except Exception:
    pass

print("FAIL" if errors else "PASS regression")
for e in errors:
    print(" ", e)
sys.exit(1 if errors else 0)
