# Green Valley Primary Care Clinic

A Python Flask web app for a primary care clinic with patient search, patient detail views with clinical handoff notes, and an admin dashboard. Uses hardcoded sample data with a Northern Lights light/dark theme.

## Run & Operate

- `python artifacts/clinic/app.py` — run the Flask clinic app directly (workflow uses `python app.py` from `artifacts/clinic/`)
- `pnpm --filter @workspace/api-server run dev` — run the shared API server (port 8080)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages

## Stack

- Python 3.11 + Flask (clinic web app)
- Jinja2 templates + vanilla CSS/JS (no frontend build step)
- pnpm workspaces, Node.js 24, TypeScript 5.9 (shared infra)
- API: Express 5 (shared API server, unused by clinic for now)
- DB: PostgreSQL + Drizzle ORM (available, not yet used by clinic)

## Where things live

- `artifacts/clinic/app.py` — Flask routes and all hardcoded patient/admin data
- `artifacts/clinic/templates/` — Jinja2 templates (base.html, search.html, patient.html, admin.html)
- `artifacts/clinic/.replit-artifact/artifact.toml` — service config (port 20964, paths `/`)

## Architecture decisions

- **Python Flask instead of React/Vite** — the user requested a Flask app; the artifact was scaffolded as react-vite for registration then patched via `verifyAndReplaceArtifactToml` to run `python app.py`.
- **All CSS inline in base.html** — self-contained, no static asset pipeline needed for a server-rendered Flask app.
- **Dark/light theme via `data-theme` attribute** — CSS variables on `:root[data-theme]`, toggled client-side, persisted in `localStorage`.
- **Hardcoded data** — patient records live in `app.py` PATIENTS list; no database yet.

## Product

- **Page 1 (/):** Patient Search — centered search bar, live client-side filtering of 3 sample patients.
- **Page 2 (/patient/<id>):** Patient Detail — demographics, vitals, conditions, medications, past notes on the left; Clinical Handoff Note form and AI Clinical Summary placeholder on the right.
- **Page 3 (/admin):** Admin Dashboard — stat cards (patients viewed, summaries generated, failed), Chart.js bar chart, recent activity log table.
- **Theme toggle** top-right on every page; Northern Lights palette (primary `#34a85a`, bg `#f9f9fa` / `#1a1d23`).

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- The `artifacts/clinic` workflow runs as `python app.py` (working directory is `artifacts/clinic/`). Do NOT use `python artifacts/clinic/app.py` — that path doubles the prefix.
- Flask templates are in `artifacts/clinic/templates/` relative to `app.py`; Flask resolves them from the script's directory automatically.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
