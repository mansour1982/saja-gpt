# ✏️ Saja GPT

Een oefen-app voor Nederlandse spelling (groep 6), met 2394 woorden uit 25 categorieën.

Werkt op iPad, telefoon, schoolcomputer en laptop — en onthoudt de sterwoorden.

---

## Wat kan de app?

- **25 categorieën** met in totaal 2394 woorden, plus "alle categorieën door elkaar".
- **Nederlandse stem** uit meegeleverde MP3's, dus overal precies dezelfde uitspraak —
  ook op een schoolcomputer zonder Nederlandse stem geïnstalleerd.
- **Snelheid instellen** (🐢 langzaam → 🐇 snel), zowel op het startscherm als tijdens het oefenen.
- **Letter-voor-letter feedback** bij een fout antwoord, zodat je precies ziet welke letter mis is.
- **Vertaalhints** in het Engels 🇬🇧 en Arabisch 🇸🇦 na elk antwoord.
- **Sterwoorden** ⭐ per categorie — moeilijke woorden worden automatisch met een ster gemarkeerd
  en kunnen apart geoefend worden.
- **Offline** te gebruiken nadat de app één keer geladen is.
- **Installeerbaar** op het beginscherm van een iPad of telefoon (PWA).

---

## 1. De app online zetten (GitHub Pages — gratis)

> Doe dit één keer, vanaf deze Mac.

De map is al een git-repository met één commit. Wat nog moet gebeuren:

### a. Log in met je persoonlijke GitHub-account

In dit terminalvenster staat `GH_TOKEN` ingesteld voor je werkaccount. Dat moet eerst weg,
anders blijft `gh` je werkaccount gebruiken:

```bash
unset GH_TOKEN
gh auth login --hostname github.com --git-protocol https --web
```

Kies bij de vragen: **GitHub.com** → **HTTPS** → **Yes** (git authenticeren) → **Login with a web browser**.
Log in de browser in als **mansour1982** en plak de code die de terminal toont.

Controleer daarna:

```bash
gh auth status
```

Er moet `Logged in to github.com account mansour1982` staan.

### b. Repository maken en pushen

```bash
cd ~/Desktop/saja-web
unset GH_TOKEN
gh repo create saja-gpt --public --source=. --remote=origin --push
```

> De repository moet **public** zijn, want GitHub Pages is alleen gratis voor publieke
> repositories. Er staan geen persoonlijke gegevens in — alleen woordenlijsten en geluid.

### c. GitHub Pages aanzetten

```bash
gh api -X POST repos/mansour1982/saja-gpt/pages \
  -f 'source[branch]=main' -f 'source[path]=/'
```

Lukt dat niet, doe het dan met de hand:
**github.com/mansour1982/saja-gpt** → **Settings** → **Pages** →
Source: **Deploy from a branch** → Branch: **main** / **(root)** → **Save**.

Na een paar minuten staat de app op:

```
https://mansour1982.github.io/saja-gpt/
```

### d. Op de iPad zetten

Open die link in **Safari** → knop **Deel** → **Zet op beginscherm**.
De app opent daarna als een echte app, zonder adresbalk.

---

## 2. Voortgang delen tussen apparaten (optioneel, gratis)

Zonder deze stap werkt alles gewoon, maar blijven de sterwoorden op één apparaat.
Wil je dat de sterwoorden van de iPad ook op de laptop verschijnen, dan is er één
gratis database nodig.

### a. Firebase-project maken

1. Ga naar <https://console.firebase.google.com> en log in met een Google-account.
2. **Add project** → naam bijv. `saja-gpt` → Google Analytics mag **uit** → **Create project**.
3. Links in het menu: **Build** → **Realtime Database** → **Create Database**.
4. Kies een locatie (bijv. *europe-west1*) → start in **test mode** → **Enable**.
5. Bovenaan staat nu een adres zoals:
   `https://saja-gpt-default-rtdb.europe-west1.firebasedatabase.app`
   Dat adres heb je zo nodig.

### b. Regels instellen

Tabblad **Rules**, plak dit en klik **Publish**:

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

> Iedereen die de geheime code raadt kan bij de sterwoorden. Kies daarom een code die
> niemand gokt, bijvoorbeeld `saja-7f3k9q2m`. Er staan alleen woorden in — geen namen,
> geen wachtwoorden.

### c. In de app invullen

Open de app → knop **☁️ Voortgang delen tussen apparaten** →
vul het **Firebase-adres** en dezelfde **geheime code** in → **💾 Opslaan & testen**.

Doe dat op **elk** apparaat met exact dezelfde twee waarden. Vanaf dan worden de
sterwoorden samengevoegd: een woord dat op de iPad een ster krijgt, heeft hem ook
op de laptop.

---

## Woorden aanpassen

De woordenlijst staat in `data.json`. Nieuwe woorden toevoegen betekent ook nieuwe
geluidsbestanden maken. Vraag me daarvoor — het is één script.

---

## Bestanden

| Bestand | Wat het doet |
|---|---|
| `index.html` | De schermen (start, oefenen, uitslag, instellingen) |
| `styles.css` | De vormgeving |
| `app.js` | Alle logica |
| `data.json` | Woordenlijsten + vertalingen + geluidsnamen |
| `audio/` | 2394 Nederlandse MP3's (20 MB) |
| `sw.js` | Zorgt dat de app offline werkt |
| `manifest.webmanifest` | Maakt installeren op het beginscherm mogelijk |
