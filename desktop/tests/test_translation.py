import json, os, shutil, sys, tempfile

REPO_DESKTOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_SRC = os.path.join(REPO_DESKTOP, "dictee_mac2.py")

WORK = "/tmp/dt_trans"
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
shutil.copy(APP_SRC, os.path.join(WORK, "dnew.py"))
shutil.copy(os.path.join(REPO_DESKTOP, "Saja_spelling.csv"), os.path.join(WORK, "Saja_spelling.csv"))
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
d.TRANSLATION_PATH = os.path.join(WORK, "vert.json")
json.dump({"huis": "house", "boompje": "", "katten": "cat"},
          open(d.TRANSLATION_PATH, "w", encoding="utf-8"))
d.SPEECH_CACHE_DIR = os.path.join(WORK, "cache")
d.gTTS_available = False
d.speak_async = lambda *a, **k: None
d.prefetch_speech = lambda *a, **k: None

errors = []
app = d.SpellingApp()
app.report_callback_exception = lambda *a: errors.append(repr(a))


def texts(widget):
    out = []
    for child in widget.winfo_children():
        try:
            out.append(child.cget("text"))
        except Exception:
            pass
        out.extend(texts(child))
    return out


def steps():
    try:
        # Unit-level checks of the lookup helper.
        assert app.translation_for("huis") == "house", app.translation_for("huis")
        assert app.translation_for("Huis") == "house"
        # Morphological fallback: 'huisje' -> 'huis'.
        assert app.translation_for("huisje") == "house", app.translation_for("huisje")
        # Unknown word -> empty, never an exception.
        assert app.translation_for("zzzqqq") == ""
        assert app.translation_for("") == ""
        assert app.translation_for(None) == ""
        # Empty gloss must be treated as unknown.
        assert app.translation_for("boompje") == ""

        # Drive a real session.
        app.start_quiz(custom_words=["huis", "katten", "zzzqqq"])
        app.update()
        app.session_words = [dict(w) for w in app.session_words]
        idx = {w["word"]: i for i, w in enumerate(app.session_words)}

        # 1. Correct answer on a word WITH a translation.
        app.current_index = idx["huis"]
        app.show_practice_screen()
        app.update()
        app.entry_box.delete(0, "end")
        app.entry_box.insert(0, "huis")
        app.check_answer()
        app.update()
        fb = texts(app.feedback_zone)
        assert any("In het Engels: house" in t for t in fb), fb

        # 2. Wrong answer on a word WITH a translation.
        app.current_index = idx["katten"]
        app.show_practice_screen()
        app.update()
        app.entry_box.delete(0, "end")
        app.entry_box.insert(0, "katen")
        app.check_answer()
        app.update()
        fb = texts(app.feedback_zone)
        assert any("Jij typte:" in t for t in fb), fb
        assert any("In het Engels: cat" in t for t in fb), fb

        # 3. Word WITHOUT a translation degrades gracefully (no line, no crash).
        app.current_index = idx["zzzqqq"]
        app.show_practice_screen()
        app.update()
        app.entry_box.delete(0, "end")
        app.entry_box.insert(0, "zzzqqq")
        app.check_answer()
        app.update()
        fb = texts(app.feedback_zone)
        assert not any("In het Engels" in t for t in fb), fb

        # 4. Missing translation file must not break anything.
        app.translations = {}
        app.current_index = idx["huis"]
        app.show_practice_screen()
        app.update()
        app.entry_box.delete(0, "end")
        app.entry_box.insert(0, "huis")
        app.check_answer()
        app.update()
        assert not any("In het Engels" in t for t in texts(app.feedback_zone))

        # 5. Navigation still works after the feedback card grew.
        app.next_word()
        app.update()
        app.previous_word()
        app.update()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        app.after(100, app.destroy)


app.after(300, steps)
try:
    app.mainloop()
except Exception:
    pass

print("FAIL" if errors else "PASS translation hint")
for e in errors:
    print(" ", e)
sys.exit(1 if errors else 0)
