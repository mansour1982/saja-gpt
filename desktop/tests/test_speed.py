import os, shutil, sys

# Resolve the app from this repository, so the tests do not depend on where the
# checkout happens to live or on a shortcut existing on the Desktop.
REPO_DESKTOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_SRC = os.path.join(REPO_DESKTOP, "dictee_mac2.py")

WORK = "/tmp/dt_spd"
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
shutil.copy(APP_SRC, os.path.join(WORK, "dnew.py"))
shutil.copy(os.path.join(REPO_DESKTOP, "Saja_spelling.csv"), os.path.join(WORK, "Saja_spelling.csv"))
shutil.copy(os.path.join(REPO_DESKTOP, "Saja_vertalingen.json"),
            os.path.join(WORK, "Saja_vertalingen.json"))
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
spoken = []
d.speak_async = lambda t, r, v: spoken.append((t, r))
d.prefetch_speech = lambda *a, **k: None

errors = []
app = d.SpellingApp()
app.report_callback_exception = lambda *a: errors.append(repr(a))


def steps():
    try:
        app.update()
        # Home screen still starts at Normaal.
        assert abs(app.speed_val.get() - 1.0) < 1e-6, app.speed_val.get()
        assert "Normaal" in app.speed_lbl.cget("text"), app.speed_lbl.cget("text")

        app.start_quiz(custom_words=["afkomst", "afrekenen", "afschuw"])
        app.update()

        # The slider must exist AND be visible on the practice screen.
        lbl = app.speed_lbl
        assert lbl.winfo_exists(), "speed_lbl gone"
        assert lbl.winfo_ismapped(), "speed_lbl not mapped"
        row = lbl.master
        assert row.winfo_ismapped() and row.winfo_width() > 200, row.winfo_width()
        scales = [c for c in row.winfo_children()
                  if c.winfo_class() == "TScale"]
        assert len(scales) == 1, [c.winfo_class() for c in row.winfo_children()]
        assert scales[0].winfo_ismapped(), "scale not mapped"
        assert scales[0].winfo_width() > 80, scales[0].winfo_width()

        # Changing the slider mid-quiz updates the label...
        app.speed_val.set(0.4)
        app.update_speed_label()
        app.update()
        assert "langzaam" in app.speed_lbl.cget("text").lower(), app.speed_lbl.cget("text")

        # ...and the new rate is actually used for the next playback.
        spoken.clear()
        app.speak_current_word()
        app.update()
        assert spoken and abs(spoken[-1][1] - 0.4) < 1e-6, spoken

        # The setting survives navigation between words.
        app.next_word(); app.update()
        assert abs(app.speed_val.get() - 0.4) < 1e-6
        assert app.speed_lbl.winfo_ismapped(), "speed_lbl lost after next_word"
        app.previous_word(); app.update()
        assert app.speed_lbl.winfo_ismapped(), "speed_lbl lost after previous_word"

        # Answering still works with the extra row present.
        app.entry_box.delete(0, "end")
        app.entry_box.insert(0, app.current_item["word"])
        app.check_answer()
        app.update()
        assert app.current_item["status"] == "correct"

        # Back home: welcome slider still reflects the changed value.
        app.show_welcome_screen()
        app.update()
        assert abs(app.speed_val.get() - 0.4) < 1e-6
        assert app.speed_lbl.winfo_ismapped(), "home speed_lbl not mapped"
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        app.after(100, app.destroy)


app.after(400, steps)
try:
    app.mainloop()
except Exception:
    pass

print("FAIL" if errors else "PASS speed-in-quiz")
for e in errors:
    print(" ", e)
sys.exit(1 if errors else 0)
