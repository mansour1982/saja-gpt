# ✏️ Saja GPT

A Dutch spelling practice app for Groep 6, with 2394 words across 25 categories.

Runs on iPad, phone, school computer and laptop — and remembers the starred words.

> The app's own interface is in Dutch, because that is the language Saja is
> practising. This README, and any error messages, are in English.

---

## What the app does

- **25 categories** with 2394 words in total, plus an "all categories mixed" option.
- **Dutch voice** from bundled MP3 files, so the pronunciation is identical everywhere —
  including a school computer with no Dutch voice installed.
- **Adjustable speed** (🐢 slow → 🐇 fast), on both the start screen and during practice.
- **Letter-by-letter feedback** on a wrong answer, showing exactly which letter is off.
- **Translation hints** in English 🇬🇧 and Arabic 🇸🇦 after each answer.
- **Starred words** ⭐ per category — words are starred automatically when they go wrong,
  and can be practised separately.
- **Works offline** once the app has loaded a first time.
- **Installable** on the home screen of an iPad or phone (PWA).

---

## 1. Publishing the app (GitHub Pages — free)

> Do this once, from this Mac.

The folder is already a git repository with commits in place. What remains:

### a. Sign in with your personal GitHub account

This terminal has `GH_TOKEN` set for your work account. It has to be cleared first,
otherwise `gh` keeps using the work account:

```bash
unset GH_TOKEN
gh auth login --hostname github.com --git-protocol https --web
```

Answer the prompts: **GitHub.com** → **HTTPS** → **Yes** (authenticate git) →
**Login with a web browser**. Sign in as **mansour1982** and paste the code shown
in the terminal.

Then verify:

```bash
gh auth status
```

It must report `Logged in to github.com account mansour1982`.

### b. Create the repository and push

```bash
cd ~/Desktop/saja-web
unset GH_TOKEN
gh repo create saja-gpt --public --source=. --remote=origin --push
```

> The repository has to be **public**, because GitHub Pages is only free for public
> repositories. Nothing personal is stored in it — only word lists and audio.

### c. Turn on GitHub Pages

```bash
gh api -X POST repos/mansour1982/saja-gpt/pages \
  -f 'source[branch]=main' -f 'source[path]=/'
```

If that fails, do it by hand:
**github.com/mansour1982/saja-gpt** → **Settings** → **Pages** →
Source: **Deploy from a branch** → Branch: **main** / **(root)** → **Save**.

After a few minutes the app is live at:

```
https://mansour1982.github.io/saja-gpt/
```

### d. Put it on the iPad

Open that link in **Safari** → **Share** button → **Add to Home Screen**.
It then opens like a real app, with no address bar.

---

## 2. Sharing progress between devices (optional, free)

Everything works without this step, but starred words stay on one device.
To make the iPad's stars show up on the laptop too, you need one free database.

### a. Create a Firebase project

1. Go to <https://console.firebase.google.com> and sign in with a Google account.
2. **Add project** → name it e.g. `saja-gpt` → Google Analytics can be **off** → **Create project**.
3. In the left menu: **Build** → **Realtime Database** → **Create Database**.
4. Pick a location (e.g. *europe-west1*) → start in **test mode** → **Enable**.
5. At the top you now see an address such as:
   `https://saja-gpt-default-rtdb.europe-west1.firebasedatabase.app`
   You will need that address in a moment.

### b. Set the rules

Open the **Rules** tab, paste this and click **Publish**:

```json
{
  "rules": {
    "saja": {
      "$code": {
        ".read": true,
        ".write": true
      }
    }
  }
}
```

> Anyone who guesses the secret code can reach the starred words, so pick a code
> nobody would guess, for example `saja-7f3k9q2m`. Only words are stored — no names,
> no passwords.

### c. Enter it in the app

Open the app → **☁️ Voortgang delen tussen apparaten** →
fill in the **Firebase address** and the same **secret code** → **💾 Opslaan & testen**.

Do this on **every** device with exactly the same two values. From then on the starred
words are merged: a word starred on the iPad is starred on the laptop too.

---

## Changing the word list

The word list lives in `data.json`. Adding new words also means generating new audio
files. Ask me for that — it is a single script.

---

## Files

| File | Purpose |
|---|---|
| `index.html` | The screens (home, practice, result, settings) |
| `styles.css` | Styling |
| `app.js` | All application logic |
| `data.json` | Word lists, translations and audio file names |
| `audio/` | 2394 Dutch MP3 files (20 MB) |
| `sw.js` | Makes the app work offline |
| `manifest.webmanifest` | Allows installing to the home screen |

---

## The desktop version

There is also a macOS version, `~/Desktop/dictee_mac2.py`, kept in step with this
web app. It reads `Saja_spelling.csv` from the folder it is stored in, so it can be
launched from any directory:

```bash
python3 ~/Desktop/dictee_mac2.py
```
