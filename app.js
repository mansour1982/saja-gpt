/* ===================================================================
   Saja GPT - spelling dictation for Groep 6
   Works offline; progress optionally syncs across devices via Firebase.
   =================================================================== */
"use strict";

const ALL_MIX = "🌍 Alle categorieën door elkaar";
const LS_STARS = "saja.stars";
const LS_SYNC = "saja.sync";
const LS_SPEED = "saja.speed";
const LS_TRACK = "saja.track";

const COMPLIMENTS = [
  "Goed gedaan!", "Top!", "Wat knap!", "Super!", "Helemaal goed!",
  "Prima werk!", "Je kunt het!", "Fantastisch!", "Wauw, knap hoor!",
];

const state = {
  data: null,
  stars: new Set(),
  sync: null,             // {url, code}
  speed: 1.0,
  track: true,
  words: [],              // [{word, status, typed, attempts, firstTry}]
  index: 0,
  label: "",
  totalAtStart: 0,
  awaitingNext: false,
  totalAttempts: 0,
  audioToken: 0,
  audio: null,
  player: null,
  audioUnlocked: false,
};

/* ---------------------------------------------------------------
   Tiny helpers
   --------------------------------------------------------------- */
const $ = (id) => document.getElementById(id);
const app = () => $("app");

function show(tplId) {
  const tpl = $(tplId);
  const node = tpl.content.cloneNode(true);
  app().innerHTML = "";
  app().appendChild(node);
}

function lsGet(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch (e) {
    return fallback;
  }
}

function lsSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    /* private mode / full disk: stay silent, app still works */
  }
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

/* ---------------------------------------------------------------
   Word data
   --------------------------------------------------------------- */
function categoryNames() {
  return Object.keys(state.data.categories);
}

function allWords() {
  const seen = new Set();
  const out = [];
  for (const list of Object.values(state.data.categories)) {
    for (const w of list) {
      const k = w.toLowerCase();
      if (!seen.has(k)) { seen.add(k); out.push(w); }
    }
  }
  return out;
}

function wordsForCategory(cat) {
  if (!cat || cat === ALL_MIX) return allWords();
  return (state.data.categories[cat] || []).slice();
}

function starredForCategory(cat) {
  return wordsForCategory(cat).filter((w) => state.stars.has(w.toLowerCase()));
}

function translation(word, table) {
  if (!table) return "";
  const w = (word || "").trim().toLowerCase();
  let g = table[w];
  if (g) return g;
  // Forgiving fallbacks so simple inflections still show a hint.
  const suffixes = ["tje", "etje", "pje", "je", "en", "s", "e"];
  for (const suf of suffixes) {
    if (w.endsWith(suf) && w.length - suf.length >= 3) {
      const stem = w.slice(0, w.length - suf.length);
      for (const cand of [stem, stem + "e", stem.length > 3 ? stem.slice(0, -1) : stem]) {
        g = table[cand];
        if (g) return g;
      }
    }
  }
  return "";
}

/* ---------------------------------------------------------------
   Letter comparison (same rules as the desktop app)
   --------------------------------------------------------------- */
function diffLetters(typed, correct) {
  const t = [];
  const c = [];
  const n = Math.max(typed.length, correct.length);
  for (let i = 0; i < n; i++) {
    const a = typed[i];
    const b = correct[i];
    if (a !== undefined) t.push([a, a === b]);
    if (b !== undefined) c.push([b, a === b]);
  }
  return [t, c];
}

/* ---------------------------------------------------------------
   Speech: pre-made MP3 first, browser voice as fallback
   --------------------------------------------------------------- */

function audioUrl(word) {
  const id = state.data.audio && state.data.audio[word.toLowerCase()];
  return id ? "audio/" + id + ".mp3" : null;
}

// iOS Safari only allows audio that starts inside a real user gesture. We keep
// ONE <audio> element for the whole app and unlock it on the first tap, so every
// later playback (including auto-speak on a new word) is allowed.
function audioElement() {
  if (!state.player) {
    const a = new Audio();
    a.preload = "auto";
    a.playsInline = true;
    state.player = a;
  }
  return state.player;
}

function unlockAudio() {
  if (state.audioUnlocked) return;
  state.audioUnlocked = true;
  const a = audioElement();
  a.muted = true;
  const p = a.play();
  if (p && typeof p.catch === "function") p.catch(() => {});
  try { a.pause(); } catch (e) { /* ignore */ }
  a.muted = false;
  try { window.speechSynthesis.getVoices(); } catch (e) { /* ignore */ }
}

function stopSpeech() {
  state.audioToken++;
  if (state.player) {
    try { state.player.pause(); } catch (e) { /* ignore */ }
  }
  state.audio = null;
  try { window.speechSynthesis.cancel(); } catch (e) { /* ignore */ }
}

function speakBrowser(word, token) {
  if (!("speechSynthesis" in window)) return;
  try {
    const u = new SpeechSynthesisUtterance(word);
    u.lang = "nl-NL";
    u.rate = Math.max(0.4, Math.min(1.4, state.speed));
    const voices = window.speechSynthesis.getVoices() || [];
    const nl = voices.find((v) => /^nl/i.test(v.lang));
    if (nl) u.voice = nl;
    if (token === state.audioToken) window.speechSynthesis.speak(u);
  } catch (e) { /* nothing else we can do */ }
}

function speak(word) {
  if (!word) return;
  stopSpeech();
  const token = state.audioToken;

  const url = audioUrl(word);
  if (!url) { speakBrowser(word, token); return; }
  const a = audioElement();
  a.onerror = () => {
    if (token === state.audioToken) speakBrowser(word, token);
  };
  a.src = url;
  a.currentTime = 0;
  a.playbackRate = Math.max(0.5, Math.min(1.4, state.speed));
  state.audio = a;
  const p = a.play();
  if (p && typeof p.catch === "function") {
    p.catch(() => {
      if (token === state.audioToken) speakBrowser(word, token);
    });
  }
}

function prefetch(words) {
  for (const w of words) {
    const url = w ? audioUrl(w) : null;
    if (!url) continue;
    const a = new Audio();
    a.preload = "auto";
    a.src = url;
  }
}

/* ---------------------------------------------------------------
   Starred words + cross-device sync
   --------------------------------------------------------------- */
function saveStars() {
  lsSet(LS_STARS, [...state.stars].sort());
  pushStars();
}

function syncEndpoint() {
  if (!state.sync || !state.sync.url || !state.sync.code) return null;
  const base = state.sync.url.replace(/\/+$/, "");
  const code = encodeURIComponent(state.sync.code.trim());
  return `${base}/saja/${code}.json`;
}

async function pullStars() {
  const url = syncEndpoint();
  if (!url) return { ok: false, reason: "off" };
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) return { ok: false, reason: "http " + r.status };
    const body = await r.json();
    const remote = (body && body.starred) || [];
    let added = 0;
    for (const w of remote) {
      const k = String(w).trim().toLowerCase();
      if (k && !state.stars.has(k)) { state.stars.add(k); added++; }
    }
    if (added) lsSet(LS_STARS, [...state.stars].sort());
    return { ok: true, added, remote: remote.length };
  } catch (e) {
    return { ok: false, reason: String(e.message || e) };
  }
}

async function pushStars() {
  const url = syncEndpoint();
  if (!url) return { ok: false, reason: "off" };
  try {
    const r = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ starred: [...state.stars].sort(), updated: Date.now() }),
    });
    return r.ok ? { ok: true } : { ok: false, reason: "http " + r.status };
  } catch (e) {
    return { ok: false, reason: String(e.message || e) };
  }
}

/* Merge local + remote, then write the union back. */
async function syncNow() {
  const pulled = await pullStars();
  if (!pulled.ok) return pulled;
  const pushed = await pushStars();
  return pushed.ok ? { ok: true, added: pulled.added } : pushed;
}

/* ---------------------------------------------------------------
   Speed label
   --------------------------------------------------------------- */
function speedText() {
  const v = state.speed;
  if (v <= 0.5) return "🐢 Heel langzaam";
  if (v <= 0.75) return "🚶 Rustig";
  if (v <= 1.0) return "🙂 Normaal";
  return "🐇 Snel";
}

function wireSpeed(sliderId, labelId) {
  const s = $(sliderId);
  const l = $(labelId);
  if (!s) return;
  s.value = String(state.speed);
  if (l) l.textContent = speedText();
  s.addEventListener("input", () => {
    state.speed = parseFloat(s.value);
    lsSet(LS_SPEED, state.speed);
    if (l) l.textContent = speedText();
  });
}

/* ---------------------------------------------------------------
   HOME
   --------------------------------------------------------------- */
function showHome() {
  stopSpeech();
  show("tpl-home");

  const sel = $("category");
  for (const name of [ALL_MIX, ...categoryNames()]) {
    const o = document.createElement("option");
    o.value = name;
    o.textContent = name;
    sel.appendChild(o);
  }
  sel.value = lsGet("saja.cat", ALL_MIX);

  const refresh = () => {
    const cat = sel.value;
    const total = wordsForCategory(cat).length;
    const starred = starredForCategory(cat).length;
    $("cat-count").textContent = `Deze categorie heeft ${total} woorden.`;
    $("star-note").textContent = starred
      ? `⭐ Je hebt hier ${starred} sterwoord${starred === 1 ? "" : "en"} om te oefenen.`
      : "⭐ Nog geen sterwoorden in deze categorie.";
    $("btn-all").textContent = `Alle ${total} woorden`;
    $("btn-star").textContent = `⭐ ${starred} sterwoorden`;
    $("btn-star").disabled = starred === 0;
    lsSet("saja.cat", cat);
  };

  let mode = lsGet("saja.mode", "all");
  const markMode = () => {
    $("btn-all").classList.toggle("btn-blue", mode === "all");
    $("btn-all").classList.toggle("btn-grey", mode !== "all");
    $("btn-star").classList.toggle("btn-yellow", mode === "star");
    $("btn-star").classList.toggle("btn-grey", mode !== "star");
    $("count-hint").textContent = mode === "star"
      ? "Je oefent alleen je sterwoorden van deze categorie."
      : "Je oefent alle woorden van deze categorie.";
  };

  sel.addEventListener("change", () => { refresh(); markMode(); });
  $("btn-all").addEventListener("click", () => { mode = "all"; lsSet("saja.mode", mode); markMode(); });
  $("btn-star").addEventListener("click", () => { mode = "star"; lsSet("saja.mode", mode); markMode(); });

  $("track").checked = state.track;
  $("track").addEventListener("change", () => {
    state.track = $("track").checked;
    lsSet(LS_TRACK, state.track);
  });

  wireSpeed("speed", "speed-label");
  $("btn-testvoice").addEventListener("click", () => speak("hallo, dit is de stem"));
  $("btn-start").addEventListener("click", () => startQuiz(sel.value, mode));
  $("btn-settings").addEventListener("click", showSettings);

  $("sync-state").textContent = syncEndpoint()
    ? "☁️ Voortgang wordt gedeeld tussen apparaten."
    : "📱 Voortgang wordt alleen op dit apparaat bewaard.";

  refresh();
  markMode();
}

/* ---------------------------------------------------------------
   QUIZ
   --------------------------------------------------------------- */
function startQuiz(cat, mode) {
  let pool;
  if (mode === "star") {
    pool = starredForCategory(cat);
    if (!pool.length) {
      alert("Nog geen sterwoorden in deze categorie.\n\n" +
            "Woorden die fout gaan komen hier vanzelf bij te staan.");
      return;
    }
    state.label = "⭐ " + (cat === ALL_MIX ? "Alle categorieën" : cat);
  } else {
    pool = wordsForCategory(cat);
    state.label = cat === ALL_MIX ? "Alle categorieën" : cat;
  }
  if (!pool.length) {
    alert("Deze categorie heeft geen woorden.");
    return;
  }

  state.words = shuffle(pool).map((w) => ({
    word: w.toLowerCase(), status: "new", typed: "", attempts: 0, firstTry: false,
  }));
  state.index = 0;
  state.totalAtStart = state.words.length;
  state.totalAttempts = 0;
  showPractice();
  prefetch(state.words.slice(0, 6).map((i) => i.word));
}

const current = () => state.words[state.index] || null;
const firstTryCorrect = () => state.words.filter((w) => w.firstTry).length;
const correctCount = () => state.words.filter((w) => w.status === "correct").length;
const answeredCount = () => state.words.filter((w) => w.status !== "new").length;

function unfinishedIndexes() {
  const n = state.words.length;
  if (!n) return [];
  const out = [];
  for (let step = 1; step <= n; step++) {
    const i = (state.index + step) % n;
    const w = state.words[i];
    const done = state.track ? w.status === "correct" : w.status !== "new";
    if (!done) out.push(i);
  }
  return out;
}

function sessionFinished() {
  return state.words.length > 0 && unfinishedIndexes().length === 0;
}

function scoreText() {
  return `⭐ ${firstTryCorrect()} / ${state.totalAtStart}`;
}

function showPractice() {
  show("tpl-practice");
  const item = current();

  $("chip").textContent = "📖 " + state.label;
  $("score").textContent = scoreText();

  const done = correctCount();
  const total = state.totalAtStart || 1;
  $("prog").style.width = Math.round((done / total) * 100) + "%";
  $("prog-text").textContent =
    `Woord ${state.index + 1} van de ${state.totalAtStart}      ✔️ ${done} goed`;

  const status = item ? item.status : "new";
  $("prompt").textContent = {
    new: "Typ hier het woord:",
    correct: "✔️ Dit woord had je goed — je mag het nog eens proberen:",
    wrong: "❌ Dit woord ging fout — probeer het opnieuw:",
  }[status];
  $("entry-border").style.background = {
    new: "var(--blue-lt)", correct: "var(--green)", wrong: "var(--red)",
  }[status];

  const entry = $("entry");
  entry.value = "";
  entry.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); handleEnter(); }
  });
  setTimeout(() => entry.focus(), 50);

  wireSpeed("speed2", "speed-label2");

  $("btn-listen").addEventListener("click", () => speak(item ? item.word : ""));
  $("btn-prev").addEventListener("click", previousWord);
  $("btn-skip").addEventListener("click", skipWord);
  $("btn-stop").addEventListener("click", showHome);
  $("btn-starword").addEventListener("click", toggleStar);
  $("btn-action").addEventListener("click", () => {
    if (sessionFinished()) showResult();
    else if (state.awaitingNext) nextWord();
    else checkAnswer();
  });

  state.awaitingNext = false;
  refreshStarButton();
  refreshNav();
  refreshAction();

  stopSpeech();
  const token = ++state.audioToken;
  setTimeout(() => { if (token === state.audioToken && item) speak(item.word); }, 350);
  prefetch(state.words.slice(state.index, state.index + 4).map((i) => i.word));
}

function handleEnter() {
  const entry = $("entry");
  if (state.awaitingNext) {
    if (sessionFinished()) showResult(); else nextWord();
  } else if (!entry.value.trim()) {
    speak(current() ? current().word : "");
  } else {
    checkAnswer();
  }
}

function refreshAction() {
  const b = $("btn-action");
  if (!b) return;
  b.classList.remove("btn-green", "btn-blue", "btn-purple");
  if (sessionFinished()) {
    b.textContent = "🏁 Bekijk je score";
    b.classList.add("btn-purple");
  } else if (state.awaitingNext) {
    b.textContent = "Volgende ➡️";
    b.classList.add("btn-blue");
  } else {
    b.textContent = "✅ Nakijken";
    b.classList.add("btn-green");
  }
}

function refreshNav() {
  const many = state.words.length > 1;
  $("btn-prev").disabled = !many;
  $("btn-skip").disabled = !many;
}

function refreshStarButton() {
  const item = current();
  const b = $("btn-starword");
  if (!b || !item) return;
  const on = state.stars.has(item.word);
  b.textContent = on ? "⭐ Ster staat aan" : "☆ Zet ster aan";
  b.classList.toggle("btn-yellow", on);
  b.classList.toggle("btn-grey", !on);
}

function toggleStar() {
  const item = current();
  if (!item) return;
  if (state.stars.has(item.word)) state.stars.delete(item.word);
  else state.stars.add(item.word);
  saveStars();
  refreshStarButton();
}

function checkAnswer() {
  const entry = $("entry");
  const typed = entry.value.trim().toLowerCase();
  const item = current();
  if (!item) return;
  if (!typed) { speak(item.word); return; }

  entry.readOnly = true;
  state.awaitingNext = true;
  state.totalAttempts++;
  item.attempts++;
  item.typed = typed;
  if (item.attempts === 1 && typed === item.word) item.firstTry = true;

  const fb = $("feedback");
  fb.innerHTML = "";
  const box = document.createElement("div");

  if (typed === item.word) {
    item.status = "correct";
    $("entry-border").style.background = "var(--green)";
    box.className = "fb ok";
    const h = document.createElement("h3");
    h.textContent = "🎉 " + pick(COMPLIMENTS);
    const w = document.createElement("p");
    w.className = "word";
    w.textContent = item.word;
    box.append(h, w);
    addHints(box, item.word);
  } else {
    item.status = "wrong";
    $("entry-border").style.background = "var(--red)";
    state.stars.add(item.word);
    saveStars();

    box.className = "fb no";
    const h = document.createElement("h4");
    h.textContent = "🧐 Bijna! Kijk goed naar de letters:";
    box.appendChild(h);

    const [tm, cm] = diffLetters(typed, item.word);
    box.appendChild(letterRow("Jij typte:", tm));
    box.appendChild(letterRow("Goed is:", cm));
    addHints(box, item.word);

    const note = document.createElement("p");
    note.className = "note";
    note.textContent = state.track
      ? "Je komt vanzelf nog een keer bij dit woord terug 🔁"
      : "Onthoud dit woord goed!";
    box.appendChild(note);
    speak(item.word);
  }

  fb.appendChild(box);
  refreshStarButton();
  refreshNav();
  refreshAction();
  $("score").textContent = scoreText();
}

function letterRow(label, marks) {
  const row = document.createElement("div");
  row.className = "letters";
  const lab = document.createElement("span");
  lab.className = "lab";
  lab.textContent = label;
  row.appendChild(lab);
  for (const [ch, ok] of marks) {
    const s = document.createElement("span");
    s.className = "lt " + (ok ? "good" : "bad");
    s.textContent = ch;
    row.appendChild(s);
  }
  return row;
}

function addHints(box, word) {
  const pairs = [
    ["🇬🇧 In het Engels: ", translation(word, state.data.en), "hint"],
    ["🇸🇦 In het Arabisch: ", translation(word, state.data.ar), "hint ar"],
  ];
  for (const [prefix, gloss, cls] of pairs) {
    if (!gloss) continue;
    const p = document.createElement("p");
    p.className = cls;
    p.textContent = prefix + gloss;
    box.appendChild(p);
  }
}

function nextWord() {
  if (state.words.length < 2) { showPractice(); return; }
  state.index = (state.index + 1) % state.words.length;
  showPractice();
}

function previousWord() {
  if (state.words.length < 2) { showPractice(); return; }
  state.index = (state.index - 1 + state.words.length) % state.words.length;
  showPractice();
}

function skipWord() {
  nextWord();
}

/* ---------------------------------------------------------------
   RESULT
   --------------------------------------------------------------- */
function showResult() {
  stopSpeech();
  show("tpl-result");

  const got = firstTryCorrect();
  const total = state.totalAtStart || 1;
  const pct = got / total;

  let emoji = "🌟", title = "Goed geoefend!";
  if (pct >= 0.9) { emoji = "🏆"; title = "Wauw, bijna alles goed!"; }
  else if (pct >= 0.7) { emoji = "🎉"; title = "Heel knap gedaan!"; }
  else if (pct >= 0.5) { emoji = "💪"; title = "Goed bezig!"; }
  else { emoji = "🌱"; title = "Blijf oefenen, je groeit!"; }

  $("result-emoji").textContent = emoji;
  $("result-title").textContent = title;
  $("result-compliment").textContent = pick(COMPLIMENTS);
  $("result-score").textContent = `${got} van de ${total} in één keer goed`;

  const wrong = state.words.filter((w) => !w.firstTry).map((w) => w.word);
  const card = $("wrong-card");
  const list = $("wrong-list");
  if (!wrong.length) {
    card.style.display = "none";
  } else {
    for (const w of wrong) {
      const chip = document.createElement("span");
      chip.className = "wordchip";
      chip.textContent = w;
      list.appendChild(chip);
    }
  }

  $("btn-again").addEventListener("click", () => {
    state.words = shuffle(state.words.map((w) => w.word)).map((w) => ({
      word: w, status: "new", typed: "", attempts: 0, firstTry: false,
    }));
    state.index = 0;
    state.totalAtStart = state.words.length;
    showPractice();
  });
  $("btn-home").addEventListener("click", showHome);
}

/* ---------------------------------------------------------------
   SETTINGS / SYNC
   --------------------------------------------------------------- */
function showSettings() {
  stopSpeech();
  show("tpl-settings");

  $("fb-url").value = (state.sync && state.sync.url) || "";
  $("fb-code").value = (state.sync && state.sync.code) || "";
  const total = state.stars.size;
  $("star-total").textContent = `Je hebt ${total} sterwoord${total === 1 ? "" : "en"} bewaard.`;

  $("btn-save-sync").addEventListener("click", async () => {
    const url = $("fb-url").value.trim();
    const code = $("fb-code").value.trim();
    if (!url || !code) {
      $("sync-msg").textContent = "Vul allebei de velden in.";
      return;
    }
    state.sync = { url, code };
    lsSet(LS_SYNC, state.sync);
    $("sync-msg").textContent = "Bezig met testen…";
    const res = await syncNow();
    $("sync-msg").textContent = res.ok
      ? `✅ Gelukt! ${res.added ? res.added + " woorden opgehaald." : "Alles is bijgewerkt."}`
      : `❌ Niet gelukt (${res.reason}). Controleer het adres en de regels in Firebase.`;
    $("star-total").textContent = `Je hebt ${state.stars.size} sterwoorden bewaard.`;
  });

  $("btn-clear-sync").addEventListener("click", () => {
    state.sync = null;
    lsSet(LS_SYNC, null);
    $("fb-url").value = "";
    $("fb-code").value = "";
    $("sync-msg").textContent = "Synchroniseren staat uit.";
  });

  $("btn-sync-now").addEventListener("click", async () => {
    $("sync-msg").textContent = "Bezig…";
    const res = await syncNow();
    $("sync-msg").textContent = res.ok
      ? `✅ Klaar. ${res.added ? res.added + " nieuwe woorden opgehaald." : "Alles was al bij."}`
      : `❌ Niet gelukt (${res.reason}).`;
    $("star-total").textContent = `Je hebt ${state.stars.size} sterwoorden bewaard.`;
  });

  $("btn-clear-stars").addEventListener("click", () => {
    if (!confirm("Weet je het zeker? Alle sterwoorden worden gewist.")) return;
    state.stars.clear();
    saveStars();
    $("star-total").textContent = "Je hebt 0 sterwoorden bewaard.";
  });

  $("btn-back").addEventListener("click", showHome);
}

/* ---------------------------------------------------------------
   Boot
   --------------------------------------------------------------- */
async function boot() {
  state.stars = new Set(lsGet(LS_STARS, []));
  state.sync = lsGet(LS_SYNC, null);
  state.speed = lsGet(LS_SPEED, 1.0);
  state.track = lsGet(LS_TRACK, true);

  try {
    const r = await fetch("data.json", { cache: "default" });
    state.data = await r.json();
  } catch (e) {
    app().innerHTML =
      '<div class="card"><h2>Oeps</h2><p class="muted">De woordenlijst kon niet geladen worden. ' +
      "Controleer je internetverbinding en probeer het opnieuw.</p></div>";
    return;
  }

  showHome();
  // Merge any progress made on other devices, quietly.
  if (syncEndpoint()) {
    const res = await pullStars();
    if (res.ok && res.added) showHome();
  }
}

document.addEventListener("DOMContentLoaded", boot);
["pointerdown", "touchstart", "keydown"].forEach((evt) => {
  document.addEventListener(evt, unlockAudio, { once: true, capture: true });
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  });
}
