# Osmora — RO Membrane Selection & Preliminary System Design

A local web application that screens commercial reverse-osmosis (RO) membranes against a client's feed water,
operating limits and published evidence, and produces a preliminary recommendation and a technical PDF report.

- **Client workspace**: guided 5-step input, ranked recommendation, plain-language warnings, charts, PDF report.
- **Admin console** (`/admin`): submissions review, membrane/source management, verification, CSV import, CSV/Excel export, backups, audit log, methodology.
- **Offline and deterministic**: no AI service or API key; no client data leaves the machine.

> **Preliminary design support only.** Estimates are indicative and derived from manufacturer ratings and published
> research under stated assumptions. They are not certified manufacturer projections and do not replace detailed
> engineering, supplier projections or pilot testing. Passing software tests shows the code implements the documented
> equations; it does **not** validate the model against real RO performance.

---

## 1. Requirements (Windows)

- Python 3.11+ (`python --version`)
- Node.js 18+ and npm (`node --version`) — only needed to build the client

## 2. First-time setup

Open PowerShell in the project folder (`C:\Mithuna\Phavi\ro_membrane`):

```powershell
# Backend dependencies
cd backend
python -m pip install -r requirements.txt

# Configure the admin account (edit the values!)
Copy-Item .env.example .env
notepad .env

# Create the database and load the starter dataset
python scripts\init_db.py
cd ..

# Build the client
cd frontend
npm install
npm run build
cd ..
```

For a hashed admin password instead of plain text: `python backend\scripts\hash_password.py` and put the printed
`RO_ADMIN_PASSWORD_HASH=...` line in `backend\.env` (remove `RO_ADMIN_PASSWORD`).

> This installation already has a generated `backend\.env` with a random admin password — open the file to read it,
> and change it before sharing the machine.

## 3. Run

**Single server (recommended)** — serves the built client and the API on one port:

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> (client) and <http://127.0.0.1:8000/admin> (admin). API docs: <http://127.0.0.1:8000/api/docs>.

Or simply run `.\start.ps1` from the project folder (builds the client if needed, initialises the DB, starts the server).

**Development mode** (hot reload) — two terminals:

```powershell
# Terminal 1
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# Terminal 2
cd frontend
npm run dev        # http://127.0.0.1:5173 (proxies /api to port 8000)
```

## 3b. Deploy to Vercel

Vercel runs the API as serverless functions with no persistent disk, so the deployment uses a hosted **Postgres**
database (Neon, via Vercel's Storage tab) instead of the local SQLite file. Files: `vercel.json`, `api/index.py`,
root `requirements.txt`, `.vercelignore` (keeps `backend/.env`, local databases and `deploy/` out of the upload).

1. `npx vercel login` and `npx vercel link` (creates the project).
2. Vercel dashboard → project → **Storage** → create a **Neon Postgres** database and connect it to the project
   (this sets `DATABASE_URL`).
3. Project → Settings → **Environment Variables** (Production): `RO_SECRET_KEY`, `RO_ADMIN_USERNAME`,
   `RO_ADMIN_PASSWORD_HASH` — values are in `deploy/production-secrets.local.txt` (never commit that file).
4. `npx vercel --prod`. The first request creates the schema and loads the starter dataset.

Hosted differences: session cookies are `Secure`; the app refuses to start without `RO_SECRET_KEY`; the admin
"Create backup" button is disabled — use Neon's backups / point-in-time restore and the Excel export; login throttling
is per serverless instance. Local development is unchanged (SQLite) unless `DATABASE_URL` is set.

## 4. Tests and checks

```powershell
cd backend
python -m pytest -q          # 60 tests: calculations, engine rules, API, auth/CSRF, export, report, persistence
cd ..\frontend
npm run typecheck            # TypeScript
npm run build                # production build
```

## 5. Data, backup and restore

- Database: `backend\data\ro_membrane.db` (SQLite, created automatically; persists across restarts).
- Backup: admin console → *Import / export* → *Create backup*, or `python backend\scripts\backup_db.py`.
  Snapshots are written to `backend\backups\` using SQLite's online-backup API (safe while running).
- Restore: stop the server, copy a backup over `backend\data\ro_membrane.db` (delete any `ro_membrane.db-wal` /
  `-shm` files next to it), then start the server. Schema migrations run automatically on start-up.
- Reset to the starter dataset: stop the server, delete `backend\data\ro_membrane.db*`, run `python backend\scripts\init_db.py`.

## 6. Architecture

```
backend/
  app/engine/        Deterministic, DB-free calculation & recommendation engine
    units.py         Unit conversions
    hydraulics.py    Flow balance, rejection, osmotic pressure, flux, permeance, required pressure
    chemistry.py     LSI, silica, SDI, oxidant, boron, completeness screening
    evidence.py      Provenance-aware parameter resolution and conflict detection
    recommend.py     Screening checks, status tiers, lexicographic ranking, client view
  app/models.py      SQLAlchemy entities (membranes, specs, observations, sources, submissions, audit, sessions)
  app/migrations.py  Versioned schema/seed migrations (schema_version table)
  app/seed_data.py   Starter dataset with full provenance
  app/api/           public.py (client, token-scoped) and admin.py (session + CSRF protected)
  app/services/      PDF report, CSV/Excel export, ORM↔engine bridge
  tests/             pytest suite
frontend/            React + Vite + TypeScript + Tailwind + Recharts + Lucide
```

**Security**: admin credentials come from environment variables (bcrypt-hashed in memory or supplied as a hash);
server-side sessions in an HttpOnly, SameSite=Strict signed cookie; a CSRF token header is required on every
state-changing admin request; login throttling; client submissions are only reachable via an unguessable per-assessment
token (no listing endpoint); the server binds to `127.0.0.1` by default. Do not expose it to the internet without a
reverse proxy with TLS (and then set `RO_COOKIE_SECURE=true`).

## 7. Engineering method (summary)

The full methodology is in the admin console (*Methodology*) and the report's technical appendix. The client dashboard
deliberately shows no equations.

1. Validate inputs; compute flow balance `Qf = Qp/r`, `Qc = Qf − Qp`.
2. System checks: feed-flow limit; osmotic floor (idealised concentrate osmotic pressure vs available pressure).
3. Chemistry screening: LSI (TDS ≤ 10,000 mg/L only), concentrate silica, SDI, oxidants, boron, completeness.
4. Per membrane: application/category compatibility, documented max pressure, temperature, pH, chlorine, SDI/turbidity
   limits; apparent permeance `A = J_rated/(P_test − π̄_test)` from the rated test point; indicative feed pressure
   `max(J/A + π̄, π_conc) + losses` (range with 0.85·A); rough permeate `Cp ≈ C̄(1 − R/100)`; test-condition comparability.
5. Status: hard failure → *Unsuitable*; missing critical evidence → *Insufficient evidence*; cautions/unknowns →
   *Conditional*; otherwise *Suitable for preliminary evaluation*. A missing limit never counts as a pass.
6. Ranking is lexicographic (status tier, open issues, unknowns, client priority, evidence, condition distance) — no weighted
   score. If nothing is suitable or conditional, the result is **No supported recommendation**.

Policy thresholds (10% pressure margin, ×/÷3 salinity comparability, LSI TDS cut-off, 100 mg/L silica screen) are engine
choices, documented as such, not literature values.

## 8. Starter dataset and provenance

Sources: the supplied review report (`_Research_Task_Evidence-Based_Reverse_Osmosis_Me.pdf`, Figs. 8–9) and five
manufacturer datasheets whose text was extracted and read on 2026-10-10:

| Datasheet (verified) | Values stored |
|---|---|
| Dow FilmTec BW30-400/34i (Form 609-00481-0910) | area, flow, rejection, test conditions, all operating limits |
| Dow FilmTec SW30HR-380 (Form 609-00390 Rev. 0, 2016) | as above |
| DuPont FilmTec SW30XLE-440 (Form 45-D00966-en Rev. 4, 2019) | as above + boron rejection |
| Hydranautics SWC4+ (10/07/13) | as above + boron, turbidity, feed flow |
| Hydranautics ESPA-2540 (2/25/15) | as above |

Values taken from the review report are marked **report-extracted** (original paper not yet re-checked). Datasheets are
attached only to the exact model they name: e.g. the BW30-400/34i sheet is *not* transferred to "BW30-400", and the
report's "SW30-HR" (99.82%, Karan & Livingston) is kept separate from the verified SW30HR-380 (99.7%).
Models named in the review without reported values (BW30LE-440, SW30XFR-400/34, SW30ULE-440i, TM820V-400, BW30XFR rated
data) are stored with no specifications and are therefore always *Insufficient evidence* until an administrator adds
sourced values. LG SW 400 R and Toray TM820L/S have partial literature values but no verified limits.

Experimental observations (Ansari 2021 pilot, Alkatheeri 2021, Conidi 2018 FGD wastewater, Ruiz-García 2019 plant
boron, Gilabert-Oriol 2023) are stored in a separate table and are never used as ratings.

## 9. Known limitations

- Single-element-equivalent screening only; no vessel/stage modelling, pressure-drop progression, or CP film model.
- Element counts are membrane-level estimates, not a plant configuration. Documented per-element feed-flow and
  concentrate limits are checked against idealised uniform arrays only.
- The calcium-sulfate screen is indicative only (ideal ion product, no concentration polarisation, Ksp at 25 °C);
  anything without generous headroom is reported as unresolved.
- No comparison against independent manufacturer projections has been possible; see `docs/AUDIT.md`.
- No temperature correction of permeability (flagged when feed and test temperatures differ by > 5 °C).
- Osmotic pressure uses an ideal NaCl-equivalent van 't Hoff relation.
- No CaSO₄/BaSO₄/SrSO₄/CaF₂ saturation, ion-by-ion permeate, pump energy, or recovery optimisation.
- Many catalogued models still lack verified datasheet limits — add them through the admin console to broaden coverage.
- The optional AI-explanation flag (`RO_AI_EXPLANATIONS`) is a placeholder: disabled, not implemented, and never part of engineering decisions.
