import json, os, shutil, sys

REPO_DESKTOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_SRC = os.path.join(REPO_DESKTOP, "dictee_mac2.py")

WORK = "/tmp/dt_ar"
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
d.TRANSLATION_PATH = os.path.join(WORK, "en.json")
d.TRANSLATION_AR_PATH = os.path.join(WORK, "ar.json")
json.dump({"huis": "house", "katten": "cat", "alleen_en": "only"},
          open(d.TRANSLATION_PATH, "w", encoding="utf-8"))
json.dump({"huis": "\u0645\u0646\u0632\u0644", "katten": "\u0642\u0637\u0629",
           "alleen_ar": "\u0641\u0642\u0637"},
          open(d.TRANSLATION_AR_PATH, "w", encoding="utf-8"))
d.SPEECH_CACHE_DIR = os.path.join(WORK, "cache")
d.gTTS_available = False
d.speak_async = lambda *a, **k: None
d.prefetch_speech = lambda *a, **k: None

errors = []
app = d.SpellingApp()
app.report_callback_exception = lambda *a: errors.append(repr(a))


def texts(w):
    out = []
    for c in w.winfo_children():
        try:
            out.append(c.cget("text"))
        except Exception:
            pass
        out.extend(texts(c))
    return out


def hint_labels(w):
    out = []
    for c in w.winfo_children():
        try:
            t = c.cget("text")
            if "In het Engels" in t or "In het Arabisch" in t:
                out.append(c)
        except Exception:
            pass
        out.extend(hint_labels(c))
    return out


def steps():
    try:
        app.update()
        assert len(app.translations_ar) == 3, len(app.translations_ar)
        # Lookup helper handles both tables independently.
        assert app.translation_for("huis", app.translations_ar) == "\u0645\u0646\u0632\u0644"
        assert app.translation_for("huisje", app.translations_ar) == "\u0645\u0646\u0632\u0644"
        assert app.translation_for("zzz", app.translations_ar) == ""

        app.start_quiz(custom_words=["huis", "katten", "alleen_en", "alleen_ar", "zzzqqq"])
        app.update()
        app.session_words = [dict(w) for w in app.session_words]
        idx = {w["word"]: i for i, w in enumerate(app.session_words)}

        def answer(word, typed):
            app.current_index = idx[word]
            app.show_practice_screen()
            app.update()
            app.entry_box.config(state="normal")
            app.entry_box.delete(0, "end")
            app.entry_box.insert(0, typed)
            app.check_answer()
            app.update()
            return texts(app.feedback_zone)

        # 1. Correct answer: both languages shown.
        fb = answer("huis", "huis")
        assert any("In het Engels: house" in t for t in fb), fb
        assert any("In het Arabisch: \u0645\u0646\u0632\u0644" in t for t in fb), fb

        # 2. Wrong answer: both languages shown alongside the letter diff.
        fb = answer("katten", "katen")
        assert any("Jij typte:" in t for t in fb), fb
        assert any("In het Engels: cat" in t for t in fb), fb
        assert any("In het Arabisch: \u0642\u0637\u0629" in t for t in fb), fb
        # Arabic label uses the Arabic-capable font and is actually visible.
        ar = [c for c in hint_labels(app.feedback_zone)
              if "Arabisch" in c.cget("text")][0]
        assert ar.winfo_ismapped(), "arabic hint not mapped"
        assert ar.winfo_width() > 60, ar.winfo_width()
        assert app.F_ARABIC[0] in str(ar.cget("font")), ar.cget("font")

        # 3. English only -> no Arabic line, no crash.
        fb = answer("alleen_en", "alleen_en")
        assert any("In het Engels: only" in t for t in fb), fb
        assert not any("In het Arabisch" in t for t in fb), fb

        # 4. Arabic only -> no English line.
        fb = answer("alleen_ar", "alleen_ar")
        assert not any("In het Engels" in t for t in fb), fb
        assert any("In het Arabisch: \u0641\u0642\u0637" in t for t in fb), fb

        # 5. Neither -> nothing at all.
        fb = answer("zzzqqq", "zzzqqq")
        assert not any("In het" in t for t in fb), fb

        # 6. Missing Arabic file entirely must not break the English hint.
        app.translations_ar = {}
        fb = answer("huis", "huis")
        assert any("In het Engels: house" in t for t in fb), fb
        assert not any("In het Arabisch" in t for t in fb), fb

        # 7. Navigation still fine with the taller feedback card.
        app.next_word(); app.update()
        app.previous_word(); app.update()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        app.after(100, app.destroy)


app.after(400, steps)
try:
    app.mainloop()
except Exception:
    pass

print("FAIL" if errors else "PASS arabic hint")
for e in errors:
    print(" ", e)
sys.exit(1 if errors else 0)
