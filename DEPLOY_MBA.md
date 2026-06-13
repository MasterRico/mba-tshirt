# MBA deployen — Schritt-für-Schritt

Server-IP: `46.224.24.51` · Coolify: `https://ooopppmmm.com`
Voraussetzung: `_split/mba.db` existiert (Daten-Split erledigt).

---

## Schritt 1 — Repo aus dem KDP-Ordner lösen & auf GitHub pushen

Der `mba/`-Ordner liegt aktuell im KDP-Repo. Raus damit an einen eigenen Ort:

```powershell
# mba/ an eigenen Ort verschieben (inkl. scripts/, OHNE _split/)
Move-Item "C:\Users\alexa\Claude\Projects\KDP Ads Platform\mba" "C:\Users\alexa\Claude\Projects\mba-tshirt"
cd "C:\Users\alexa\Claude\Projects\mba-tshirt"

git init -b main
git add .
git commit -m "Initial MBA T-Shirt Factory (split from combined platform)"
```

GitHub-Repo anlegen und pushen (GitHub CLI):

```powershell
gh repo create MasterRico/mba-tshirt --private --source . --remote origin --push
```

Oder manuell: Repo `MasterRico/mba-tshirt` auf github.com anlegen, dann:

```powershell
git remote add origin https://github.com/MasterRico/mba-tshirt.git
git push -u origin main
```

> `_split/` und `mba.db` NICHT committen — sind durch `.gitignore` (`*.db`) ausgeschlossen, bleiben aber im KDP-Ordner liegen.

---

## Schritt 2 — DNS-Records anlegen

Beim DNS-Provider von `ooopppmmm.com` zwei A-Records auf die Server-IP:

| Typ | Name | Wert |
|---|---|---|
| A | `mba` | `46.224.24.51` |
| A | `mcp.mba` | `46.224.24.51` |

Kurz warten bis auflösbar: `nslookup mba.ooopppmmm.com` → muss `46.224.24.51` zeigen.

---

## Schritt 3 — Coolify: neue Application

1. Coolify → **+ New** → **Public/Private Repository** → Repo `MasterRico/mba-tshirt`, Branch `main`.
   (GitHub-App `git-hub-master-rico-claude` wiederverwenden, falls Zugriff besteht.)
2. **Build Pack: Docker Compose**, Base Directory `/`, Compose-File `/docker-compose.yml`.
3. Server: `localhost` (derselbe Hetzner-Server).
4. Projekt: neues Projekt **„MBA T-Shirt"** (sauber getrennt von „MBA & KDP Portal").

### Domains
- **Domains for frontend**: `https://mba.ooopppmmm.com`
- **Domains for mcp**: `https://mcp.mba.ooopppmmm.com`
- backend: leer lassen (intern)

### Environment Variables
Setzen (Werte teils aus der bestehenden KDP-App übernehmbar):

| Variable | Wert |
|---|---|
| `API_TOKEN` | **neu generieren** (`openssl rand -hex 32`) — eigener Token für MBA |
| `SECRET_KEY` | **neu generieren** (`openssl rand -hex 32`) |
| `MCP_PUBLIC_URL` | `https://mcp.mba.ooopppmmm.com` |
| `TSF_ANTHROPIC_API_KEY` | aus KDP-App übernehmen |
| `TSF_ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` (optional) |
| `TSF_AMAZON_MARKETPLACE` | aus KDP-App (z. B. `com`/`de`) |
| `TSF_RESEARCH_INTERVAL_HOURS` | aus KDP-App (z. B. `24`) |
| `TSF_MBA_TIER` | aus KDP-App (z. B. `100`) |

> Empfehlung: eigener `API_TOKEN`/`SECRET_KEY` für MBA (echte Trennung). Wenn du
> denselben wie KDP nimmst, geht's auch — dann sind beide Dienste über denselben
> Token erreichbar.

5. **Deploy** klicken. Erstdeploy legt das Volume an und erzeugt eine leere `mba.db`.

---

## Schritt 4 — Echte Daten laden (mba.db)

Nach dem ersten Deploy die leere DB durch die gesplittete ersetzen.

**4a — mba.db auf den Server laden** (lokale PowerShell):
```powershell
scp "C:\Users\alexa\Claude\Projects\KDP Ads Platform\_split\mba.db" root@46.224.24.51:/tmp/mba.db
```

**4b — auf dem Server einspielen** (SSH):
```bash
# Neue MBA-Backend-Container-ID finden (jetzt gibt es mehrere backend-*)
docker ps --format '{{.Names}}' | grep backend

# MBA-Volume finden (neben dem KDP-Volume nxhoq...)
docker volume ls | grep db-data
```
MBA-Stack in Coolify **Stop** klicken, dann:
```bash
# Variante A (robust): direkt ins Volume kopieren
cp /tmp/mba.db /var/lib/docker/volumes/<MBA-VOLUME-NAME>/_data/mba.db

# Variante B: per docker cp in den (gestoppten) Container
# docker cp /tmp/mba.db <MBA-BACKEND-CONTAINER>:/app/data/mba.db
```
In Coolify **Start/Redeploy**.

---

## Schritt 5 — Verifizieren (KDP bleibt unangetastet)

- `https://mba.ooopppmmm.com` lädt, Token-Gate → mit `API_TOKEN` einloggen → Dashboard zeigt Nischen/Designs (20 Nischen, 345 Prompts).
- `https://mcp.mba.ooopppmmm.com/healthz` → `{"status":"ok"}`.
- MCP-Tools (`tsf_dashboard` etc.) als neuen Connector testen.
- Gegencheck: `https://kdp.ooopppmmm.com` läuft normal weiter (noch mit TSF-Resten — die entfernen wir in Phase 4).

Wenn alles grün ist → Phase 4: TSF aus dem KDP-Repo entfernen + `kdp_ads_clean.db` einspielen.
