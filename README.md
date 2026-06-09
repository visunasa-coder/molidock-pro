# MoliDock Pro

MoliDock Pro is a full-stack scaffold for an integrated drug discovery and vaccine design web application. It includes:

- React/Vite frontend with a unified Design Studio for small-molecule drug discovery and vaccine construct planning.
- Docking submission, job polling, ADMET descriptors, authenticated downloads, and 3D pose viewing.
- Vaccine workflow planning for antigen intake, homology checks, epitope screening, population coverage, construct design, structure validation, and reporting.
- Live official IEDB API adapters for MHC-I, MHC-II, and linear B-cell epitope prediction.
- Official NCBI Protein search/fetch and asynchronous blastp homology handoff.
- Persisted vaccine projects with sequence profiling, candidate ranking, multi-epitope assembly, reverse translation, and downloadable reports.
- FastAPI backend with JWT auth, SQLite/Postgres-ready persistence, per-plan quotas, Stripe checkout scaffolding, async docking jobs, and generated reports.
- Real engine adapters for AutoDock Vina, Open Babel, and optional receptor preparation tooling.

Important: no code can make docking or vaccine design "errorless." This system is designed to be robust and auditable, and it refuses to fabricate scientific docking scores when Vina is not installed unless `ALLOW_DEMO_DOCKING=true` is explicitly set for demos.

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
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
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

Open [http://127.0.0.1:5180](http://127.0.0.1:5180).

## Workflow

1. Register a user in the frontend.
2. Open Design Studio and choose Drug discovery or Vaccine design.

Drug discovery:

2. Upload a receptor as `.pdb` or `.pdbqt`.
3. Upload a ligand as `.sdf`, `.mol2`, `.pdb`, or `.pdbqt`, or provide SMILES.
4. Set grid center, box size, exhaustiveness, and number of modes.
5. Start docking and wait for the queued job to complete.
6. Load the PDBQT pose in the 3D viewer or download the Markdown report, pose, log, and result JSON.

Vaccine design:

1. Search NCBI Protein or paste an antigen FASTA sequence.
2. Create a persisted vaccine project and run the integrated IEDB MHC-I, MHC-II, MHC-I processing, and BepiPred-2.0 analysis.
3. Review deterministic physicochemical and sequence-liability calculations.
4. Select ranked candidates and assemble a linker-separated multi-epitope construct.
5. Export protein/DNA FASTA, result JSON, and the Markdown evidence report.
6. Submit NCBI blastp and review conservation or host-homology results after the provider completes the job.
7. Complete the external validation gates documented in the project report.

## IEDB Predictor Integration

The backend calls the official [IEDB Analysis Resource API](https://tools.iedb.org/main/tools-api/) and normalizes its TSV output into JSON:

- `POST /vaccine/predict/mhc` for MHC-I and MHC-II predictions.
- `POST /vaccine/predict/bcell` for linear B-cell predictions.
- `POST /vaccine/predict/processing` for MHC-I processing predictions.
- `/vaccine/projects` for persisted integrated analyses and construct artifacts.
- `/vaccine/source/*` for NCBI Protein search and FASTA retrieval.

Configuration:

```text
IEDB_TOOLS_BASE_URL=https://tools-cluster-interface.iedb.org/tools_api
IEDB_TIMEOUT_SECONDS=90
IEDB_MAX_PREDICTIONS=20000
IEDB_RESULT_LIMIT=500
VACCINE_MAX_SEQUENCE_AA=5000
NCBI_TOOL=MoliDockPro
NCBI_EMAIL=
NCBI_API_KEY=
NCBI_TIMEOUT_SECONDS=60
```

Antigen sequences submitted through predictor or homology endpoints are transmitted to IEDB or NCBI. Do not submit confidential or regulated sequences without an approved data-sharing policy.

## Deployment

The repository contains:

- `frontend/vercel.json` for Vite SPA deployment and deep-link routing on Vercel.
- `render.yaml` for a free Render Docker web service.
- `backend/Dockerfile` with Open Babel and AutoDock Vina 1.2.7.

Production endpoints:

```text
Frontend: https://molidock-pro.vercel.app
Backend:  https://molidock-pro-1.onrender.com
```

Set `VITE_API_URL` in Vercel if the backend URL changes. Set `CORS_ORIGINS` in Render to the exact production frontend origins.

The free Render service has an ephemeral filesystem. SQLite data and generated artifacts can be lost when the service redeploys or restarts. For durable production use, configure `DATABASE_URL` with persistent Postgres and move generated artifacts to object storage. Free Render Postgres expires after 30 days, so it is suitable only for evaluation.

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
- Epitope scores and percentile ranks are computational prioritization signals, not experimental proof of immunogenicity, safety, or protective efficacy.
- BepiPred linear regions require structural accessibility and laboratory validation.
- Sequence liability flags are transparent rules, not antigenicity, allergenicity, or toxicity predictions.
- AutoDock Vina performs small-molecule docking and is not a valid replacement for protein-protein docking or immune simulation.
- Reverse-translated DNA uses a fixed preferred-codon table and is not vendor-grade expression optimization.
- Do not market the platform as diagnostic, clinical, or guaranteed-accurate without validated studies and legal review.
