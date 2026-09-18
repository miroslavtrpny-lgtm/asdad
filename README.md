# byt-bot

Bot, ktorý 24/7 sleduje **Bazoš.cz** a **Sreality.cz** (predaj bytov, celá ČR) a
pri každom novom inzeráte do zadanej ceny pošle správu na Telegram s adresou,
dispozíciou, cenou, odkazom a odhadom, či je byt obsadený nájomníkom.

## Ako to funguje

- `src/bazos.py` a `src/sreality.py` sťahujú aktuálne inzeráty priamo z verejných
  stránok (Bazoš cez HTML, Sreality cez JSON vstavaný v stránke) a filtrujú podľa ceny.
- `src/tenant.py` sa pokúsi z textu inzerátu odhadnúť, či je byt obsadený nájomníkom
  ("s nájemníkem", "pronajato"...) alebo voľný ("volný ihned"...). **Toto pole nie je
  na žiadnej zo stránok štruktúrované, takže ide len o odhad z textu — nie vždy to
  vyjde.**
- `data/seen.json` si pamätá, ktoré inzeráty už boli odoslané, aby sa neposielali
  opakovane. Pri úplne prvom behu sa všetky aktuálne inzeráty len "označia ako videné"
  bez odoslania (inak by prišlo naraz aj niekoľko stoviek správ).
- `src/main.py` spustí jedno kolo kontroly (nie je to nekonečná slučka) — o
  opakované spúšťanie každých pár minút sa stará GitHub Actions (pozri nižšie).

## 1. Vytvorenie Telegram bota

1. V Telegrame napíš **@BotFather** → `/newbot` → zvoľ meno a username bota.
2. BotFather ti dá **token** v tvare `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.
3. Napíš svojmu novému botovi akúkoľvek správu (napr. "ahoj"), aby si mu "otvoril" chat.
4. Zisti svoje **chat ID** — otvor v prehliadači:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   (namiesto `<TOKEN>` daj skutočný token) a v JSON nájdi `"chat":{"id": ...}`.
   Ak chceš posielať do skupiny, pridaj bota do skupiny a namiesto toho použi
   záporné chat ID skupiny.

## 2. Lokálne vyskúšanie

```bash
cd byt-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# doplň TELEGRAM_BOT_TOKEN a TELEGRAM_CHAT_ID do .env
export $(grep -v '^#' .env | xargs)
python -m src.main
```

Prvý beh len naplní `data/seen.json` (bez správ na Telegram). Spusti príkaz
znova (pokojne aj ručne zmaž jeden riadok z `data/seen.json`, aby si vyskúšal
reálne odoslanie) a over, že správa príde.

## 3. Nasadenie na 24/7 beh — odporúčané: GitHub Actions (zadarmo)

Toto je najjednoduchší spôsob bez potreby vlastného servera:

1. Vytvor nový **GitHub repozitár** (odporúčam **public** — Secrets zostanú tajné
   aj vo verejnom repe, ale beh na GitHub Actions je vtedy úplne zadarmo a bez
   limitu; v súkromnom repe máš len 2000 minút/mesiac zadarmo, čo pri behu
   každých 5 minút nestačí).
2. Nahraj tam obsah tohto priečinka:
   ```bash
   cd byt-bot
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin <URL_TVOJHO_REPA>
   git push -u origin main
   ```
3. V repe choď do **Settings → Secrets and variables → Actions → New repository secret**
   a pridaj:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. Voliteľne v **Settings → Secrets and variables → Actions → Variables** pridaj
   `MAX_PRICE_CZK` (napr. `1300000`), ak chceš iný limit ako predvolený.
5. Workflow `.github/workflows/scan.yml` sa spúšťa automaticky každých 5 minút
   (`workflow_dispatch` ti navyše umožní spustiť ho ručne cez záložku **Actions**
   na vyskúšanie).

Poznámka: GitHub automaticky vypína scheduled workflows po ~60 dňoch úplnej
neaktivity repozitára. Keďže bot sám commitne `data/seen.json` vždy, keď nájde
niečo nové, repo zostáva aktívne, pokiaľ sa občas nejaký nový inzerát objaví.

### Alternatíva: vlastný server / VPS

Ak by si radšej mal kód súkromne alebo chceš kratší interval než 5 min, stačí
malý VPS (napr. lacný Hetzner/DigitalOcean droplet) a cez `cron` alebo
`systemd timer` spúšťať `python -m src.main` napr. každú 1 minútu — sťahovanie
oboch stránok trvá len pár sekúnd, takže to server takmer nezaťaží. Napíš mi,
ak chceš pomôcť aj s týmto nastavením.

## Nastavenie / limity

- Cenový limit: env premenná `MAX_PRICE_CZK` (predvolené `1 300 000`).
- Lokalita: celá Česká republika (bez obmedzenia na kraj/mesto).
- Adresa pri Bazoši je len mesto + PSC — Bazoš pri bytoch neuvádza ulicu v
  štruktúrovanej podobe, iba niekedy v texte inzerátu.
- Odhad nájomníka je best-effort z textu inzerátu, nie spoľahlivý údaj.
- Aby sa nešpecifikoval rovnaký byt viackrát: `data/seen.json` drží posledných
  6000 ID z každého zdroja.
