# MBA T-Shirt Factory

Eigenständige Plattform für die automatisierte MBA-T-Shirt-Design-Pipeline
(Research → Analyse → Design-Prompts → Compliance → Performance-Learning).

Abgespalten von der kombinierten KDP/MBA-Plattform. KDP Ads läuft separat unter
`kdp.ooopppmmm.com`.

## Architektur

Docker-Compose-Stack mit drei Services:

- **backend** — FastAPI, API unter `/api/v1/tsf/*`, SQLite-DB unter `/app/data/mba.db` (Volume `db-data`).
- **frontend** — React-SPA (Vite), serviert via nginx, proxyt `/api` → backend. Domain `mba.ooopppmmm.com`.
- **mcp** — MCP-Bridge (Streamable-HTTP), nur `tsf_*`-Tools, proxyt zum backend. Domain `mcp.mba.ooopppmmm.com`.

Externes Routing (Domains → Container) übernimmt der Coolify-Proxy.
`nginx/nginx.conf` ist ein optionaler eigenständiger Reverse-Proxy für Setups
ohne Coolify-Proxy und **nicht** in `docker-compose.yml` eingebunden.

## Setup

1. `cp .env.example .env` und Werte eintragen (`API_TOKEN`, `SECRET_KEY`, `TSF_ANTHROPIC_API_KEY`).
2. `docker compose up --build`.
3. DB liegt im Volume `db-data` unter `/app/data/mba.db`.

## Env-Variablen

| Variable | Zweck |
|---|---|
| `API_TOKEN` | Bearer-Token für `/api/v1/*` und MCP (shared) |
| `SECRET_KEY` | App-Secret |
| `MCP_PUBLIC_URL` | öffentliche MCP-URL (OAuth-Discovery) |
| `TSF_ANTHROPIC_API_KEY` | Claude API für Analyse/Prompt-Generierung |
| `TSF_ANTHROPIC_MODEL` | Claude-Modell (Default sonnet-4) |
| `TSF_AMAZON_MARKETPLACE` | Marktplatz (com, de, …) |
| `TSF_RESEARCH_INTERVAL_HOURS` | Research-Intervall |
| `TSF_MBA_TIER` | MBA-Tier (Slot-Anzahl) |

## MCP-Tools

`tsf_health`, `tsf_dashboard`, `tsf_list_designs`, `tsf_list_niches`,
`tsf_slot_summary`, `tsf_performance_summary`, `tsf_learning_insights`.
