# MoliDock Pro

MoliDock Pro is a full-stack scaffold for a subscription molecular docking web application. It includes:

- React/Vite frontend with login, docking submission, job polling, ADMET descriptors, authenticated downloads, and 3D pose viewing.
- FastAPI backend with JWT auth, SQLite/Postgres-ready persistence, per-plan quotas, Stripe checkout scaffolding, async docking jobs, and generated reports.
- Real engine adapters for AutoDock Vina, Open Babel, and optional receptor preparation tooling.

Important: no code can make molecular docking "errorless." This system is designed to be robust and auditable, and it refuses to fabricate scientific docking scores when Vina is not installed unless `ALLOW_DEMO_DOCKING=false` is explicitly set for demos.

## Project Layout

```text
molidock-pro/
  backend/
    app/
      routers/
      services/
      main.py
    requirements.txt
    .env.example
  frontend/
    src/
      App.jsx
      api.js
      styles.css
    package.json
    .env.example
```

## Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

To enable RDKit-backed ADMET descriptors:

```bash
pip install -r requirements-admet.txt
```

Install these scientific command-line tools on the host:

- AutoDock Vina, available as `vina` or configured with `VINA_BINARY`.
- Open Babel, available as `obabel` or configured with `OBABEL_BINARY`.
- Optional receptor preparation script, configured with `PREPARE_RECEPTOR_BINARY`.

For production, set a long random `SECRET_KEY`, move from SQLite to Postgres by changing `DATABASE_URL`, configure HTTPS, and replace the in-process background task runner with a queue such as Celery/RQ/Arq.

## Frontend Setup

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

## Workflow

1. Register a user in the frontend.
2. Upload a receptor as `.pdb` or `.pdbqt`.
3. Upload a ligand as `.sdf`, `.mol2`, `.pdb`, or `.pdbqt`, or provide SMILES.
4. Set grid center, box size, exhaustiveness, and number of modes.
5. Start docking and wait for the queued job to complete.
6. Load the PDBQT pose in the 3D viewer or download the Markdown report, pose, log, and result JSON.

## Subscription Hooks

The backend supports plan quotas:

- `free`: default monthly quota.
- `pro`: paid monthly quota.
- `lab`: higher monthly quota.
- `enterprise`: unlimited placeholder.

Configure Stripe values in `backend/.env`:

```text
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_LAB_PRICE_ID=price_...
```

Point the Stripe webhook to:

```text
POST /billing/webhook
```

## Scientific Guardrails

- Vina scores are docking model outputs, not experimental binding constants.
- Receptor protonation, ligand tautomer state, cofactors, waters, grid placement, and receptor flexibility must be validated.
- The generated contact table is a geometric screen, not a publication-grade interaction profiler.
- Do not market the platform as diagnostic, clinical, or guaranteed-accurate without validated studies and legal review.
