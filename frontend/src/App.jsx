import React, { useCallback, useEffect, useRef, useState } from "react";
import * as $3Dmol from "3dmol";
import {
  Activity,
  AlertTriangle,
  Beaker,
  CreditCard,
  Database,
  Dna,
  Download,
  Eye,
  FileText,
  FlaskConical,
  ListChecks,
  LogOut,
  Microscope,
  Network,
  Pill,
  Play,
  RefreshCw,
  ShieldCheck,
  Syringe,
  Target,
  TestTube,
  Upload,
  UserPlus,
  Workflow,
  Zap,
} from "lucide-react";

import {
  createCheckout,
  createDockingJob,
  createVaccineProject,
  downloadFile,
  fetchVaccineAntigen,
  getFileText,
  getJob,
  getToken,
  getVaccineProject,
  health,
  analyzeVaccineProject,
  buildVaccineConstruct,
  listJobs,
  listVaccineProjects,
  login,
  me,
  pollVaccineBlast,
  register,
  runAdmet,
  runAdmetByCompound,
  runAutoDock,
  runBcellPrediction,
  runMhcPrediction,
  runVaccinePlan,
  searchVaccineAntigens,
  setToken,
  submitVaccineBlast,
} from "./api";

const terminalStates = new Set(["completed", "failed", "canceled"]);

const navItems = [
  ["studio", Workflow, "Design Studio"],
  ["dashboard", Activity, "Dashboard"],
  ["docking", FlaskConical, "Docking"],
  ["vaccine", Syringe, "Vaccine Design"],
  ["viewer", Eye, "3D Viewer"],
  ["admet", Beaker, "ADMET"],
  ["jobs", Database, "Jobs"],
  ["billing", CreditCard, "Billing"],
];

const workflowDefinitions = {
  drug: {
    title: "Drug discovery",
    icon: Pill,
    summary: "Target selection, ligand preparation, docking, pose review, and reporting in one workspace.",
    stages: [
      ["Target intelligence", "UniProt, RCSB PDB, AlphaFold DB, binding-site grid prediction"],
      ["Ligand library", "PubChem lookup, SMILES/SDF intake, RDKit descriptors, Open Babel conversion"],
      ["Docking setup", "Receptor/ligand preparation, grid controls, exhaustiveness, and run tracking"],
      ["Docking and scoring", "AutoDock Vina jobs, exhaustiveness controls, pose and log capture"],
      ["Review package", "3D pose viewer, contact table, report, result JSON, downloadable files"],
    ],
    tools: [
      ["RCSB/PDB target fetch", "configured"],
      ["PubChem compound fetch", "configured"],
      ["Open Babel conversion", "configured"],
      ["AutoDock Vina docking", "configured"],
      ["3Dmol pose viewer", "configured"],
    ],
  },
  vaccine: {
    title: "Vaccine design",
    icon: Syringe,
    summary: "Antigen sourcing, sequence QC, epitope screening, population coverage, construct design, structure review, and reports.",
    stages: [
      ["Pathogen and antigen intake", "NCBI Protein search/fetch, FASTA cleanup, provenance, and sequence profiling"],
      ["Conservation and specificity", "NCBI blastp submission, hit review, strain coverage, and host similarity exclusion"],
      ["Epitope discovery", "IEDB MHC I, MHC II, MHC I processing, and BepiPred-2.0 candidate ranking"],
      ["Population and construct design", "HLA coverage handoff, linker assembly, reverse translation, and export"],
      ["Structure and validation", "Structure modeling, docking, immune simulation handoff, final evidence report"],
    ],
    tools: [
      ["NCBI antigen source", "configured"],
      ["Persisted construct planner", "configured"],
      ["NCBI BLAST homology module", "configured"],
      ["IEDB MHC I/II epitope module", "configured"],
      ["IEDB MHC I processing module", "configured"],
      ["IEDB B-cell epitope module", "configured"],
      ["Evidence reports and FASTA exports", "configured"],
      ["Population coverage module", "planned"],
      ["Antigenicity/allergenicity/toxicity filters", "planned"],
      ["Structure modeling handoff", "planned"],
    ],
  },
};

const platformCapabilities = [
  [FlaskConical, "Docking", "Manual receptor-ligand docking plus automatic target and compound preparation.", "docking"],
  [Syringe, "Vaccine Design", "Antigen FASTA intake, sequence QC, epitope planning gates, and construct planning.", "vaccine"],
  [Beaker, "ADMET", "Separate compound-name and SMILES descriptor workspace for drug-likeness checks.", "admet"],
  [Eye, "3D Viewer", "Pose visualization, receptor overlay, contact review, and downloadable result files.", "viewer"],
  [Database, "Jobs", "One job history for docking runs, reports, logs, and result JSON files.", "jobs"],
];

const vaccineDesignGates = [
  ["Sequence QC", "FASTA cleanup, length checks, amino-acid validation, and window generation"],
  ["Homology filter", "Pathogen conservation and host-similarity exclusion before prioritizing epitopes"],
  ["Epitope prediction", "MHC I, MHC II, and B-cell epitope modules for candidate selection"],
  ["Safety filters", "Antigenicity, allergenicity, toxicity, and physicochemical stability gates"],
  ["Population coverage", "HLA population coverage review before final construct assembly"],
  ["Construct validation", "Linkers, adjuvant plan, structure modeling handoff, docking, and final report"],
];

export default function App() {
  const [user, setUser] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [active, setActive] = useState("studio");
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState("");
  const [systemHealth, setSystemHealth] = useState(null);

  const loadJobs = useCallback(async () => {
    if (!getToken()) return;
    const rows = await listJobs();
    setJobs(rows);
    setSelectedJob((current) => {
      if (!current) return rows[0] || null;
      return rows.find((job) => job.id === current.id) || current;
    });
  }, []);

  useEffect(() => {
    async function boot() {
      try {
        const status = await health();
        setSystemHealth(status);
      } catch {
        setSystemHealth(null);
      }

      if (!getToken()) {
        setBusy(false);
        return;
      }

      try {
        const profile = await me();
        setUser(profile);
        await loadJobs();
      } catch {
        setToken("");
      } finally {
        setBusy(false);
      }
    }

    boot();
  }, [loadJobs]);

  useEffect(() => {
    if (!selectedJob || terminalStates.has(selectedJob.status)) return undefined;

    const handle = window.setInterval(async () => {
      try {
        const next = await getJob(selectedJob.id);
        setSelectedJob(next);
        setJobs((current) => current.map((job) => (job.id === next.id ? next : job)));
      } catch (error) {
        setMessage(error.message);
      }
    }, 2500);

    return () => window.clearInterval(handle);
  }, [selectedJob]);

  async function handleAuth(nextUser) {
    setUser(nextUser);
    await loadJobs();
  }

  function logout() {
    setToken("");
    setUser(null);
    setJobs([]);
    setSelectedJob(null);
  }

  function handleJobCreated(job, nextMessage = "Docking job queued") {
    setSelectedJob(job);
    setJobs((current) => [job, ...current]);
    setActive("viewer");
    setMessage(nextMessage);
  }

  if (busy) return <div className="boot">Starting MoliDock Pro</div>;
  if (!user) return <AuthScreen onAuth={handleAuth} />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <ShieldCheck size={26} />
          <div>
            <strong>MoliDock Pro</strong>
            <span>{user.plan} workspace</span>
          </div>
        </div>

        <nav className="nav-list">
          {navItems.map(([key, Icon, label]) => (
            <button
              key={key}
              className={active === key ? "nav-button active" : "nav-button"}
              onClick={() => setActive(key)}
              title={label}
            >
              <Icon size={19} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <button className="ghost-button" onClick={logout}>
          <LogOut size={18} />
          <span>Sign out</span>
        </button>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Integrated drug discovery and vaccine design system</p>
            <h1>{navItems.find(([key]) => key === active)?.[2]}</h1>
          </div>
          <button
            className="icon-button"
            onClick={async () => {
              await loadJobs();
              setMessage("Jobs refreshed");
            }}
            title="Refresh jobs"
          >
            <RefreshCw size={18} />
            <span>Refresh</span>
          </button>
        </header>

        {message && (
          <div className="toast" role="status">
            {message}
            <button onClick={() => setMessage("")}>Dismiss</button>
          </div>
        )}

        {active === "dashboard" && (
          <Dashboard jobs={jobs} selectedJob={selectedJob} health={systemHealth} />
        )}

        {active === "studio" && (
          <DesignStudioPanel
            jobs={jobs}
            health={systemHealth}
            setActive={setActive}
          />
        )}

        {active === "docking" && (
          <DockingWorkspace
            onCreated={handleJobCreated}
            onError={setMessage}
          />
        )}

        {active === "vaccine" && <VaccineDesignPanel onError={setMessage} />}
        {active === "viewer" && <ViewerPanel job={selectedJob} onError={setMessage} />}
        {active === "admet" && <AdmetPanel onError={setMessage} />}
        {active === "jobs" && (
          <JobsPanel jobs={jobs} selectedJob={selectedJob} onSelect={setSelectedJob} onRefresh={loadJobs} />
        )}
        {active === "billing" && <BillingPanel user={user} onError={setMessage} />}
      </main>
    </div>
  );
}

function AuthScreen({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        await register({ email, password, full_name: fullName });
      }

      await login(email, password);
      onAuth(await me());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-panel">
        <div className="brand large">
          <ShieldCheck size={30} />
          <div>
            <strong>MoliDock Pro</strong>
            <span>Drug discovery and vaccine design</span>
          </div>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && (
            <label>
              Full name
              <input value={fullName} onChange={(event) => setFullName(event.target.value)} autoComplete="name" />
            </label>
          )}

          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" />
          </label>

          <label>
            Password
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </label>

          {error && <div className="error-line">{error}</div>}

          <button className="primary-button" disabled={loading}>
            {mode === "login" ? <ShieldCheck size={18} /> : <UserPlus size={18} />}
            <span>{loading ? "Working" : mode === "login" ? "Sign in" : "Create account"}</span>
          </button>
        </form>

        <button className="link-button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "Create a new account" : "Use existing account"}
        </button>
      </section>
    </main>
  );
}

function DockingWorkspace({ onCreated, onError }) {
  return (
    <section className="panel-grid">
      <AutoDockPanel onCreated={(job) => onCreated(job, "Auto-docking job queued")} onError={onError} />
      <DockingPanel onCreated={onCreated} onError={onError} />
    </section>
  );
}

function Dashboard({ jobs, selectedJob, health: systemHealth }) {
  const completed = jobs.filter((job) => job.status === "completed").length;
  const running = jobs.filter((job) => ["queued", "running"].includes(job.status)).length;
  const bestAffinity = jobs
    .map((job) => job.best_affinity_kcal_mol)
    .filter((value) => typeof value === "number")
    .sort((a, b) => a - b)[0];

  return (
    <section className="panel-grid">
      <div className="metric-row">
        <Metric label="Total jobs" value={jobs.length} />
        <Metric label="Running" value={running} />
        <Metric label="Completed" value={completed} />
        <Metric label="Best affinity" value={bestAffinity ? `${bestAffinity} kcal/mol` : "--"} />
      </div>

      <section className="surface">
        <PanelTitle icon={Activity} title="Selected job" />
        {selectedJob ? <JobSummary job={selectedJob} /> : <EmptyState text="No docking jobs yet" />}
      </section>

      <section className="surface">
        <PanelTitle icon={ShieldCheck} title="Runtime health" />
        <HealthGrid health={systemHealth} />
      </section>
    </section>
  );
}

function DesignStudioPanel({ jobs, health: systemHealth, setActive }) {
  const completed = jobs.filter((job) => job.status === "completed").length;
  const activeJobs = jobs.filter((job) => ["queued", "running"].includes(job.status)).length;

  return (
    <section className="studio-layout">
      <section className="surface full-width">
        <div className="studio-heading">
          <div>
            <PanelTitle icon={Workflow} title="Integrated design studio" />
            <p className="eyebrow">Everything currently available in this integrated platform.</p>
          </div>
        </div>
      </section>

      <section className="surface full-width">
        <PanelTitle icon={ListChecks} title="Available modules" />
        <div className="capability-grid">
          {platformCapabilities.map(([Icon, title, detail, route]) => (
            <div className="capability-card" key={title}>
              <Icon size={22} />
              <div>
                <strong>{title}</strong>
                <p>{detail}</p>
              </div>
              <button className="icon-button" type="button" onClick={() => setActive(route)}>
                <span>Open</span>
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="surface">
        <PanelTitle icon={Pill} title="Drug discovery flow" />
        <p className="muted-copy">{workflowDefinitions.drug.summary}</p>
        <WorkflowStageList stages={workflowDefinitions.drug.stages} />
        <div className="studio-metrics">
          <Metric label="Total jobs" value={jobs.length} />
          <Metric label="Active jobs" value={activeJobs} />
          <Metric label="Completed jobs" value={completed} />
        </div>
      </section>

      <section className="surface">
        <PanelTitle icon={Syringe} title="Vaccine design flow" />
        <p className="muted-copy">{workflowDefinitions.vaccine.summary}</p>
        <WorkflowStageList stages={workflowDefinitions.vaccine.stages} />
      </section>

      <section className="surface full-width">
        <PanelTitle icon={ShieldCheck} title="Runtime health" />
        <HealthGrid health={systemHealth} />
      </section>
    </section>
  );
}

function VaccineDesignPanel({ onError }) {
  return (
    <section className="studio-layout">
      <section className="surface workflow-main">
        <PanelTitle icon={Syringe} title="Vaccine designing workflow" />
        <p className="muted-copy">{workflowDefinitions.vaccine.summary}</p>
        <WorkflowStageList stages={workflowDefinitions.vaccine.stages} />
      </section>

      <section className="surface">
        <PanelTitle icon={ListChecks} title="Vaccine gates" />
        <WorkflowStageList stages={vaccineDesignGates} />
      </section>

      <VaccineConstructPanel onError={onError} />
    </section>
  );
}

function WorkflowStageList({ stages }) {
  return (
    <div className="workflow-stage-list">
      {stages.map(([title, detail], index) => (
        <div className="workflow-stage" key={title}>
          <span className="stage-index">{index + 1}</span>
          <div>
            <strong>{title}</strong>
            <p>{detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function ToolMatrix({ tools, health }) {
  return (
    <div className="tool-matrix">
      {tools.map(([name, status]) => (
        <div className="tool-row" key={name}>
          <span>{name}</span>
          <StatusBadge status={resolveToolStatus(name, status, health)} />
        </div>
      ))}
    </div>
  );
}

function resolveToolStatus(name, status, health) {
  const binaries = health?.binaries || {};
  if (status !== "configured") return status;
  if (name.includes("AutoDock Vina")) return binaries.vina ? "ready" : "missing";
  if (name.includes("Open Babel")) return binaries.obabel ? "ready" : "missing";
  return "ready";
}

function VaccineConstructPanel({ onError }) {
  const [projectName, setProjectName] = useState("Candidate vaccine");
  const [constructType, setConstructType] = useState("multi-epitope");
  const [fasta, setFasta] = useState("");
  const [sourceAccession, setSourceAccession] = useState("");
  const [plan, setPlan] = useState(null);
  const [running, setRunning] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setRunning(true);
    try {
      setPlan(await runVaccinePlan({ projectName, constructType, fasta }));
    } catch (error) {
      onError(error.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="surface full-width">
      <PanelTitle icon={Dna} title="Vaccine construct planner" />

      <VaccineAntigenSourcePanel
        onSelect={(record) => {
          setFasta(record.fasta);
          setSourceAccession(record.accession);
          setProjectName(record.title || record.accession || "Candidate vaccine");
        }}
        onError={onError}
      />

      <form className="docking-form" onSubmit={submit}>
        <div className="form-grid">
          <label>
            Project name
            <input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
          </label>
          <label>
            Construct focus
            <select value={constructType} onChange={(event) => setConstructType(event.target.value)}>
              <option value="multi-epitope">Multi-epitope vaccine</option>
              <option value="mhc-i">MHC I cytotoxic T-cell screen</option>
              <option value="mhc-ii">MHC II helper T-cell screen</option>
              <option value="b-cell">Linear B-cell screen</option>
            </select>
          </label>
        </div>

        <label className="wide-field">
          Antigen FASTA sequence
          <textarea
            value={fasta}
            onChange={(event) => setFasta(event.target.value)}
            rows={6}
            placeholder=">antigen&#10;MNNQRK..."
          />
        </label>

        <button className="primary-button" type="submit" disabled={running || !fasta.trim()}>
          <Microscope size={18} />
          <span>{running ? "Building" : "Build plan"}</span>
        </button>
      </form>

      {plan && (
        <div className="construct-output">
          <div className="summary-grid">
            <Metric label="Project" value={plan.projectName} />
            <Metric label="Sequence length" value={`${plan.length} aa`} />
            <Metric label="Focus" value={labelFor(plan.constructType)} />
            <Metric label="Required gates" value={plan.requiredGates.length} />
          </div>

          <div className="workflow-stage-list compact">
            <div className="workflow-stage">
              <span className="stage-index">
                <Target size={15} />
              </span>
              <div>
                <strong>Screening windows</strong>
                <p>{plan.windows.map((item) => `${item.range} ${item.sequence}`).join(" | ")}</p>
              </div>
            </div>
            <div className="workflow-stage">
              <span className="stage-index">
                <Network size={15} />
              </span>
              <div>
                <strong>Required predictors</strong>
                <p>{plan.requiredGates.join(", ")}</p>
              </div>
            </div>
            <div className="workflow-stage">
              <span className="stage-index">
                <TestTube size={15} />
              </span>
              <div>
                <strong>Amino-acid composition</strong>
                <p>{Object.entries(plan.composition).map(([key, value]) => `${key}:${value}`).join(" ")}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      <VaccinePredictorPanel fasta={fasta} onError={onError} />
      <IntegratedVaccineProjectPanel
        projectName={projectName}
        fasta={fasta}
        sourceAccession={sourceAccession}
        onError={onError}
      />
    </section>
  );
}

function VaccineAntigenSourcePanel({ onSelect, onError }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [running, setRunning] = useState(false);
  const [fetching, setFetching] = useState("");

  async function search(event) {
    event.preventDefault();
    setRunning(true);
    try {
      const response = await searchVaccineAntigens(query);
      setResults(response.results || []);
    } catch (error) {
      onError(error.message);
    } finally {
      setRunning(false);
    }
  }

  async function choose(record) {
    setFetching(record.accession);
    try {
      const fetched = await fetchVaccineAntigen(record.accession);
      onSelect({ ...fetched, title: record.title });
    } catch (error) {
      onError(error.message);
    } finally {
      setFetching("");
    }
  }

  return (
    <div className="source-panel">
      <div className="panel-heading">
        <div>
          <h2>NCBI antigen source</h2>
          <p className="muted-copy">
            Search the official NCBI Protein database and load a public FASTA record.
          </p>
        </div>
        <StatusBadge status="ready" />
      </div>
      <form className="source-search" onSubmit={search}>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Protein, pathogen, gene, or accession"
        />
        <button className="icon-button" type="submit" disabled={running || query.trim().length < 2}>
          <Database size={18} />
          <span>{running ? "Searching" : "Search NCBI"}</span>
        </button>
      </form>
      {results.length > 0 && (
        <div className="source-results">
          {results.map((record) => (
            <button
              className="source-result"
              type="button"
              key={record.uid}
              onClick={() => choose(record)}
              disabled={Boolean(fetching)}
            >
              <span>
                <strong>{record.accession}</strong>
                <small>{record.title}</small>
              </span>
              <span>{fetching === record.accession ? "Loading" : `${record.length || "?"} aa`}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function VaccinePredictorPanel({ fasta, onError }) {
  const [predictor, setPredictor] = useState("mhc-i");
  const [alleles, setAlleles] = useState(
    "HLA-A*01:01, HLA-A*02:01, HLA-A*03:01, HLA-A*24:02",
  );
  const [peptideLength, setPeptideLength] = useState("9");
  const [rankThreshold, setRankThreshold] = useState("1");
  const [method, setMethod] = useState("recommended_epitope");
  const [prediction, setPrediction] = useState(null);
  const [running, setRunning] = useState(false);

  function changePredictor(value) {
    setPredictor(value);
    setPrediction(null);
    if (value === "mhc-i") {
      setAlleles("HLA-A*01:01, HLA-A*02:01, HLA-A*03:01, HLA-A*24:02");
      setPeptideLength("9");
      setRankThreshold("1");
    } else if (value === "mhc-ii") {
      setAlleles(
        "HLA-DRB1*01:01, HLA-DRB1*04:01, HLA-DRB1*07:01, HLA-DRB1*15:01",
      );
      setPeptideLength("15");
      setRankThreshold("10");
    }
  }

  async function submit(event) {
    event.preventDefault();
    setRunning(true);
    setPrediction(null);
    try {
      const result =
        predictor === "b-cell"
          ? await runBcellPrediction({ fasta })
          : await runMhcPrediction({
              fasta,
              mhcClass: predictor,
              alleles,
              peptideLength,
              method,
              rankThreshold,
            });
      setPrediction(result);
    } catch (error) {
      onError(error.message);
    } finally {
      setRunning(false);
    }
  }

  const sequenceLength = cleanProteinSequence(fasta).length;

  return (
    <div className="predictor-panel">
      <div className="panel-heading">
        <div>
          <h2>Live IEDB predictors</h2>
          <p className="muted-copy">
            Submit the antigen to the official IEDB MHC or linear B-cell prediction API.
          </p>
        </div>
        <StatusBadge status="ready" />
      </div>

      <form className="docking-form" onSubmit={submit}>
        <div className="form-grid">
          <label>
            Predictor
            <select value={predictor} onChange={(event) => changePredictor(event.target.value)}>
              <option value="mhc-i">MHC I peptide binding</option>
              <option value="mhc-ii">MHC II peptide binding</option>
              <option value="b-cell">Linear B-cell epitopes</option>
            </select>
          </label>

          {predictor !== "b-cell" && (
            <label>
              IEDB method
              <select value={method} onChange={(event) => setMethod(event.target.value)}>
                <option value="recommended_epitope">Recommended epitope likelihood</option>
                <option value="recommended_binding">Recommended binding affinity</option>
                <option value="recommended">IEDB recommended default</option>
              </select>
            </label>
          )}
        </div>

        {predictor !== "b-cell" && (
          <>
            <label className="wide-field">
              Human HLA alleles, comma or line separated
              <textarea
                value={alleles}
                onChange={(event) => setAlleles(event.target.value)}
                rows={3}
              />
            </label>
            <div className="form-grid">
              <label>
                Peptide length
                <input
                  type="number"
                  min={predictor === "mhc-i" ? 8 : 11}
                  max={predictor === "mhc-i" ? 15 : 30}
                  value={peptideLength}
                  onChange={(event) => setPeptideLength(event.target.value)}
                />
              </label>
              <label>
                Binder rank cutoff (%)
                <input
                  type="number"
                  min="0.1"
                  max="100"
                  step="0.1"
                  value={rankThreshold}
                  onChange={(event) => setRankThreshold(event.target.value)}
                />
              </label>
            </div>
          </>
        )}

        <div className="predictor-submit-row">
          <span>{sequenceLength.toLocaleString()} amino acids ready for submission</span>
          <button className="primary-button" type="submit" disabled={running || !fasta.trim()}>
            <Network size={18} />
            <span>{running ? "Running IEDB" : "Run predictor"}</span>
          </button>
        </div>
      </form>

      {prediction && <VaccinePredictionResults prediction={prediction} />}
    </div>
  );
}

function VaccinePredictionResults({ prediction }) {
  const isBcell = prediction.predictor === "b-cell";
  return (
    <div className="prediction-output">
      <div className="summary-grid">
        <Metric label="Provider" value={prediction.provider} />
        <Metric label="Method" value={prediction.method} />
        <Metric
          label={isBcell ? "Predicted regions" : "Rank-filtered binders"}
          value={isBcell ? prediction.regionCount : prediction.binderCount}
        />
        <Metric
          label={isBcell ? "Epitope residues" : "Total predictions"}
          value={isBcell ? prediction.epitopeResidueCount : prediction.totalPredictions}
        />
      </div>

      <p className="prediction-note">
        {prediction.scientificNote}{" "}
        <a href={prediction.providerUrl} target="_blank" rel="noreferrer">
          Provider documentation
        </a>
      </p>

      {isBcell ? (
        prediction.regions.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Range</th>
                  <th>Sequence</th>
                  <th>Length</th>
                  <th>Mean score</th>
                  <th>Max score</th>
                </tr>
              </thead>
              <tbody>
                {prediction.regions.map((region) => (
                  <tr key={`${region.start}-${region.end}`}>
                    <td>{region.start}-{region.end}</td>
                    <td className="sequence-cell">{region.sequence}</td>
                    <td>{region.length}</td>
                    <td>{region.meanScore}</td>
                    <td>{region.maxScore}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState text="IEDB returned no contiguous linear B-cell regions." />
        )
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Allele</th>
                <th>Range</th>
                <th>Peptide</th>
                <th>Core</th>
                <th>Rank %</th>
                <th>Model value</th>
                <th>Binder</th>
              </tr>
            </thead>
            <tbody>
              {prediction.results.slice(0, 100).map((result) => (
                <tr key={`${result.allele}-${result.start}-${result.peptide}`}>
                  <td>{result.allele}</td>
                  <td>{result.start}-{result.end}</td>
                  <td className="sequence-cell">{result.peptide}</td>
                  <td className="sequence-cell">{result.core}</td>
                  <td>{result.rankPercent}</td>
                  <td>
                    {result.affinityNm !== null
                      ? `${result.affinityNm} nM`
                      : result.score ?? "n/a"}
                  </td>
                  <td>
                    <StatusBadge status={result.isBinder ? "ready" : "filtered"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {prediction.results.length > 100 && (
            <p className="prediction-note">
              Showing the top 100 of {prediction.returnedPredictions} returned predictions,
              sorted by percentile rank.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function IntegratedVaccineProjectPanel({
  projectName,
  fasta,
  sourceAccession,
  onError,
}) {
  const [project, setProject] = useState(null);
  const [projects, setProjects] = useState([]);
  const [selectedCandidates, setSelectedCandidates] = useState([]);
  const [running, setRunning] = useState("");
  const [blastDatabase, setBlastDatabase] = useState("swissprot");

  const refreshProjects = useCallback(async () => {
    try {
      setProjects(await listVaccineProjects());
    } catch (error) {
      onError(error.message);
    }
  }, [onError]);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  async function createAndAnalyze() {
    setRunning("analysis");
    try {
      const created = await createVaccineProject({
        name: projectName,
        fasta,
        sourceAccession,
      });
      const analyzed = await analyzeVaccineProject(created.id);
      setProject(analyzed);
      setSelectedCandidates(
        (analyzed.results?.candidates || []).slice(0, 8).map((item) => item.id),
      );
      await refreshProjects();
    } catch (error) {
      onError(error.message);
    } finally {
      setRunning("");
    }
  }

  async function loadProject(id) {
    if (!id) {
      setProject(null);
      setSelectedCandidates([]);
      return;
    }
    setRunning("load");
    try {
      const loaded = await getVaccineProject(id);
      setProject(loaded);
      setSelectedCandidates(
        loaded.results?.construct?.selectedCandidateIds
          || (loaded.results?.candidates || []).slice(0, 8).map((item) => item.id),
      );
    } catch (error) {
      onError(error.message);
    } finally {
      setRunning("");
    }
  }

  async function buildConstruct() {
    if (!project) return;
    setRunning("construct");
    try {
      const updated = await buildVaccineConstruct(project.id, selectedCandidates);
      setProject(updated);
      await refreshProjects();
    } catch (error) {
      onError(error.message);
    } finally {
      setRunning("");
    }
  }

  async function submitBlast() {
    if (!project) return;
    setRunning("blast");
    try {
      const blast = await submitVaccineBlast(project.id, blastDatabase);
      setProject({
        ...project,
        results: { ...project.results, blast },
      });
    } catch (error) {
      onError(error.message);
    } finally {
      setRunning("");
    }
  }

  async function pollBlast() {
    if (!project) return;
    setRunning("blast-poll");
    try {
      const blast = await pollVaccineBlast(project.id);
      setProject({
        ...project,
        results: { ...project.results, blast },
      });
    } catch (error) {
      onError(error.message);
    } finally {
      setRunning("");
    }
  }

  function toggleCandidate(id) {
    setSelectedCandidates((current) =>
      current.includes(id)
        ? current.filter((candidateId) => candidateId !== id)
        : [...current, id],
    );
  }

  const results = project?.results || {};
  const profile = results.sequenceProfile;
  const candidates = results.candidates || [];
  const construct = results.construct;
  const blast = results.blast;

  return (
    <div className="integrated-vaccine-panel">
      <div className="panel-heading">
        <div>
          <h2>Integrated vaccine project</h2>
          <p className="muted-copy">
            Persist provenance, run all configured IEDB predictors, rank candidates,
            assemble a construct, submit NCBI BLAST, and export evidence artifacts.
          </p>
        </div>
        <StatusBadge status={project?.status || "planned"} />
      </div>

      <div className="project-controls">
        <label>
          Saved projects
          <select
            value={project?.id || ""}
            onChange={(event) => loadProject(event.target.value)}
          >
            <option value="">New analysis</option>
            {projects.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name} - {item.status} - {item.length} aa
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary-button"
          type="button"
          onClick={createAndAnalyze}
          disabled={Boolean(running) || !fasta.trim()}
        >
          <Play size={18} />
          <span>{running === "analysis" ? "Running full analysis" : "Run integrated analysis"}</span>
        </button>
      </div>

      {project && (
        <>
          <div className="summary-grid project-summary">
            <Metric label="Project" value={project.name} />
            <Metric label="Status" value={<StatusBadge status={project.status} />} />
            <Metric label="Length" value={`${project.length} aa`} />
            <Metric label="Candidates" value={candidates.length} />
          </div>

          {profile && (
            <div className="summary-grid">
              <Metric label="Molecular weight" value={`${profile.molecularWeightDa} Da`} />
              <Metric label="Estimated pI" value={profile.estimatedPI} />
              <Metric label="GRAVY" value={profile.gravy} />
              <Metric label="Charge at pH 7" value={profile.estimatedChargePH7} />
            </div>
          )}

          {candidates.length > 0 && (
            <div className="candidate-section">
              <div className="panel-heading">
                <div>
                  <h2>Ranked epitope candidates</h2>
                  <p className="muted-copy">
                    Select candidates for construct assembly. Every candidate still requires
                    safety and experimental review.
                  </p>
                </div>
                <span>{selectedCandidates.length} selected</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Select</th>
                      <th>Type</th>
                      <th>Allele</th>
                      <th>Range</th>
                      <th>Sequence</th>
                      <th>Rank %</th>
                      <th>Processing</th>
                      <th>Composite</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.slice(0, 100).map((candidate) => (
                      <tr key={candidate.id}>
                        <td>
                          <input
                            className="candidate-checkbox"
                            type="checkbox"
                            checked={selectedCandidates.includes(candidate.id)}
                            onChange={() => toggleCandidate(candidate.id)}
                          />
                        </td>
                        <td>{candidate.type}</td>
                        <td>{candidate.allele || "-"}</td>
                        <td>{candidate.start}-{candidate.end}</td>
                        <td className="sequence-cell">{candidate.sequence}</td>
                        <td>{candidate.rankPercent ?? "-"}</td>
                        <td>{candidate.processingScore ?? "-"}</td>
                        <td>{candidate.compositeScore}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button
                className="primary-button"
                type="button"
                onClick={buildConstruct}
                disabled={Boolean(running) || selectedCandidates.length === 0}
              >
                <Dna size={18} />
                <span>{running === "construct" ? "Assembling" : "Assemble construct"}</span>
              </button>
            </div>
          )}

          {construct && (
            <div className="construct-result">
              <div className="summary-grid">
                <Metric label="Epitopes" value={construct.epitopeCount} />
                <Metric label="Protein length" value={`${construct.proteinSequence.length} aa`} />
                <Metric label="DNA length" value={`${construct.dnaSequence.length} nt`} />
                <Metric label="GC content" value={`${construct.gcPercent}%`} />
              </div>
              <label>
                Protein construct
                <textarea value={construct.proteinSequence} rows={5} readOnly />
              </label>
            </div>
          )}

          <div className="blast-panel">
            <div>
              <strong>NCBI BLAST homology handoff</strong>
              <p>
                Submit blastp, then poll no more than once per minute. Expert review is
                required for conservation and human-homology decisions.
              </p>
            </div>
            <div className="blast-controls">
              <select
                value={blastDatabase}
                onChange={(event) => setBlastDatabase(event.target.value)}
              >
                <option value="swissprot">Swiss-Prot</option>
                <option value="refseq_protein">RefSeq Protein</option>
                <option value="nr">Non-redundant protein</option>
              </select>
              <button
                className="icon-button"
                type="button"
                onClick={submitBlast}
                disabled={Boolean(running)}
              >
                <Network size={18} />
                <span>{running === "blast" ? "Submitting" : "Submit BLAST"}</span>
              </button>
              {blast?.rid && (
                <button
                  className="icon-button"
                  type="button"
                  onClick={pollBlast}
                  disabled={Boolean(running)}
                >
                  <RefreshCw size={18} />
                  <span>{running === "blast-poll" ? "Checking" : "Check result"}</span>
                </button>
              )}
            </div>
            {blast && (
              <p className="prediction-note">
                RID {blast.rid} | Status: {blast.status} | Hits: {blast.hits?.length || 0}
              </p>
            )}
          </div>

          <div className="button-row">
            <button
              className="icon-button"
              type="button"
              disabled={!project.files?.report}
              onClick={() => downloadFile(project.files.report, `${project.id}-vaccine-report.md`)}
            >
              <Download size={18} />
              <span>Report</span>
            </button>
            <button
              className="icon-button"
              type="button"
              disabled={!project.files?.resultJson}
              onClick={() => downloadFile(project.files.resultJson, `${project.id}-vaccine-result.json`)}
            >
              <Download size={18} />
              <span>Result JSON</span>
            </button>
            <button
              className="icon-button"
              type="button"
              disabled={!project.files?.constructFasta}
              onClick={() => downloadFile(project.files.constructFasta, `${project.id}-construct.fasta`)}
            >
              <Download size={18} />
              <span>Protein FASTA</span>
            </button>
            <button
              className="icon-button"
              type="button"
              disabled={!project.files?.dnaFasta}
              onClick={() => downloadFile(project.files.dnaFasta, `${project.id}-construct-dna.fasta`)}
            >
              <Download size={18} />
              <span>DNA FASTA</span>
            </button>
          </div>

          {results.validationGaps?.length > 0 && (
            <div className="validation-gaps">
              {results.validationGaps.map((gap) => (
                <div className="workflow-stage" key={gap.gate}>
                  <span className="stage-index"><ShieldCheck size={15} /></span>
                  <div>
                    <strong>{gap.gate}</strong>
                    <p>{gap.handoff}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function DockingPanel({ onCreated, onError }) {
  const [proteinFile, setProteinFile] = useState(null);
  const [ligandFile, setLigandFile] = useState(null);
  const [ligandSmiles, setLigandSmiles] = useState("");
  const [form, setForm] = useState({
    protein_name: "Protein",
    ligand_name: "Ligand",
    center_x: "0",
    center_y: "0",
    center_z: "0",
    size_x: "20",
    size_y: "20",
    size_z: "20",
    exhaustiveness: "16",
    num_modes: "10",
  });
  const [submitting, setSubmitting] = useState(false);

  function setValue(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSubmitting(true);

    try {
      const body = new FormData();
      Object.entries(form).forEach(([key, value]) => body.set(key, value));

      if (proteinFile) body.set("protein_file", proteinFile);
      if (ligandFile) body.set("ligand_file", ligandFile);
      if (ligandSmiles.trim()) body.set("ligand_smiles", ligandSmiles.trim());

      const job = await createDockingJob(body);
      onCreated(job);
    } catch (error) {
      onError(error.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="surface docking-form" onSubmit={submit}>
      <PanelTitle icon={FlaskConical} title="Docking setup" />


      <div className="upload-row">
        <FilePicker label="Protein PDB/PDBQT" file={proteinFile} onChange={setProteinFile} required />
        <FilePicker label="Ligand SDF/MOL2/PDB/PDBQT" file={ligandFile} onChange={setLigandFile} />
      </div>

      <label className="wide-field">
        Ligand SMILES
        <textarea value={ligandSmiles} onChange={(event) => setLigandSmiles(event.target.value)} rows={3} />
      </label>


      <div className="form-grid">
        <Field label="Exhaustiveness" value={form.exhaustiveness} onChange={(value) => setValue("exhaustiveness", value)} />
        <Field label="Modes" value={form.num_modes} onChange={(value) => setValue("num_modes", value)} />
      </div>

      <button className="primary-button" disabled={submitting}>
        <Play size={18} />
        <span>{submitting ? "Queueing" : "Start docking"}</span>
      </button>
    </form>
  );
}

function ViewerPanel({ job, onError }) {
  const viewerRef = useRef(null);
  const viewerInstanceRef = useRef(null);
  const [loadingPose, setLoadingPose] = useState(false);

  async function loadPose() {
    if (!job?.files?.pose || !viewerRef.current) return;

    setLoadingPose(true);

    try {
      const poseText = await getFileText(job.files.pose);
      const receptorText = job.files.receptor ? await getFileText(job.files.receptor) : null;

      viewerRef.current.innerHTML = "";

      const viewer = $3Dmol.createViewer(viewerRef.current, {
        backgroundColor: "black",
      });

      viewerInstanceRef.current = viewer;

      if (receptorText) {
        const receptorModel = viewer.addModel(receptorText, "pdbqt");
        receptorModel.setStyle(
          {},
          {
            cartoon: {
              color: "spectrum",
            },
          }
        );
      }

      const poseModel = viewer.addModel(poseText, "pdbqt");

      poseModel.setStyle(
        {},
        {
          stick: {
            radius: 0.25,
            colorscheme: "cyanCarbon",
          },
          sphere: {
            scale: 0.25,
          },
        }
      );

      viewer.zoomTo();
      viewer.render();

      setTimeout(() => {
        viewer.resize();
        viewer.zoomTo();
        viewer.render();
      }, 300);
    } catch (error) {
      onError(error.message);
    } finally {
      setLoadingPose(false);
    }
  }

  useEffect(() => {
    function handleResize() {
      if (viewerInstanceRef.current) {
        viewerInstanceRef.current.resize();
        viewerInstanceRef.current.render();
      }
    }

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <section className="viewer-layout">
      <div className="surface">
        <PanelTitle icon={Eye} title="Pose viewer" />
        <div className="viewer-canvas" ref={viewerRef} />
        <div className="button-row">
          <button className="primary-button" onClick={loadPose} disabled={!job?.files?.pose || loadingPose}>
            <Eye size={18} />
            <span>{loadingPose ? "Loading" : "Load pose"}</span>
          </button>
          <FileButtons job={job} onError={onError} />
        </div>
      </div>

      <div className="surface">
        <PanelTitle icon={FileText} title="Result" />
        {job ? <JobSummary job={job} /> : <EmptyState text="Select a docking job" />}
      </div>

      <div className="surface full-width">
        <PanelTitle icon={Beaker} title="Contacts" />
        <ContactsTable contacts={job?.contacts || []} />
      </div>
    </section>
  );
}

function AdmetPanel({ onError }) {
  const [compound, setCompound] = useState("");
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setRunning(true);

    try {
      const data = await runAdmetByCompound(compound);
      setResult(data);
    } catch (error) {
      onError(error.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <form className="surface" onSubmit={submit}>
      <PanelTitle icon={Beaker} title="ADMET Prediction" />

      <label className="wide-field">
        Compound Name
        <input
          type="text"
          value={compound}
          onChange={(e) => setCompound(e.target.value)}
          placeholder="e.g. Aspirin, Curcumin, Erinacine A"
        />
      </label>

      <button
        className="primary-button"
        disabled={running || !compound.trim()}
      >
        <Play size={18} />
        <span>{running ? "Running..." : "Run ADMET"}</span>
      </button>

      {result && (
        <div className="metric-row admet-grid">
          {Object.entries(result).map(([key, value]) => (
            <Metric
              key={key}
              label={key.replaceAll("_", " ")}
              value={Array.isArray(value) ? value.join(", ") : String(value)}
            />
          ))}
        </div>
      )}
    </form>
  );
}

function JobsPanel({ jobs, selectedJob, onSelect, onRefresh }) {
  return (
    <section className="surface">
      <div className="panel-heading">
        <PanelTitle icon={Database} title="Docking jobs" />
        <button className="icon-button" onClick={onRefresh}>
          <RefreshCw size={18} />
          <span>Refresh</span>
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Protein</th>
              <th>Ligand</th>
              <th>Affinity</th>
              <th>Created</th>
            </tr>
          </thead>

          <tbody>
            {jobs.map((job) => (
              <tr
                key={job.id}
                className={selectedJob?.id === job.id ? "selected-row" : ""}
                onClick={() => onSelect(job)}
              >
                <td>
                  <StatusBadge status={job.status} />
                </td>
                <td>{job.protein_name}</td>
                <td>{job.ligand_name}</td>
                <td>{job.best_affinity_kcal_mol ?? "--"}</td>
                <td>{new Date(job.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {jobs.length === 0 && <EmptyState text="No jobs available" />}
      </div>
    </section>
  );
}

function BillingPanel({ user, onError }) {
  async function checkout(plan) {
    try {
      const response = await createCheckout(plan);
      window.location.href = response.checkout_url;
    } catch (error) {
      onError(error.message);
    }
  }

  return (
    <section className="billing-grid">
      {[
        ["free", "5 jobs/month", "Included"],
        ["pro", "100 jobs/month", "Subscribe"],
        ["lab", "1000 jobs/month", "Subscribe"],
      ].map(([plan, quota, action]) => (
        <div className="plan-box" key={plan}>
          <h2>{plan}</h2>
          <p>{quota}</p>
          <StatusBadge status={user.plan === plan ? "active" : "available"} />
          <button className="primary-button" disabled={user.plan === plan || plan === "free"} onClick={() => checkout(plan)}>
            <CreditCard size={18} />
            <span>{action}</span>
          </button>
        </div>
      ))}
    </section>
  );
}

function HealthGrid({ health: systemHealth }) {
  const binaries = systemHealth?.binaries || {};

  return (
    <div className="health-grid">
      {["vina", "obabel", "prepare_receptor"].map((key) => (
        <div className="health-item" key={key}>
          <span>{key.replace("_", " ")}</span>
          <StatusBadge status={binaries[key] ? "ready" : "missing"} />
        </div>
      ))}
    </div>
  );
}

function JobSummary({ job }) {
  return (
    <div className="summary-grid">
      <Metric label="Status" value={<StatusBadge status={job.status} />} />
      <Metric label="Protein" value={job.protein_name} />
      <Metric label="Ligand" value={job.ligand_name} />
      <Metric label="Best affinity" value={job.best_affinity_kcal_mol ? `${job.best_affinity_kcal_mol} kcal/mol` : "--"} />
      {job.error_message && <Metric label="Error" value={job.error_message} tone="danger" />}
      {job.warnings?.length > 0 && <Metric label="Warnings" value={job.warnings.join(" ")} tone="warning" />}
    </div>
  );
}

function ContactsTable({ contacts }) {
  if (!contacts.length) return <EmptyState text="No contacts parsed yet" />;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Residue</th>
            <th>Ligand atom</th>
            <th>Receptor atom</th>
            <th>Distance</th>
            <th>Type</th>
          </tr>
        </thead>

        <tbody>
          {contacts.map((contact, index) => (
            <tr key={`${contact.residue}-${contact.residue_number}-${index}`}>
              <td>
                {contact.residue} {contact.chain}
                {contact.residue_number}
              </td>
              <td>{contact.ligand_atom}</td>
              <td>{contact.receptor_atom}</td>
              <td>{contact.distance_angstrom} A</td>
              <td>{contact.interaction_type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FileButtons({ job, onError }) {
  if (!job) return null;

  async function download(kind, filename) {
    try {
      await downloadFile(job.files[kind], filename);
    } catch (error) {
      onError(error.message);
    }
  }

  return (
    <>
      <button className="icon-button" disabled={!job.files?.report} onClick={() => download("report", `${job.id}-report.md`)}>
        <Download size={18} />
        <span>Report</span>
      </button>

      <button className="icon-button" disabled={!job.files?.pose} onClick={() => download("pose", `${job.id}-pose.pdbqt`)}>
        <Download size={18} />
        <span>Pose</span>
      </button>
    </>
  );
}

function FilePicker({ label, file, onChange, required }) {
  return (
    <label className="file-picker">
      <Upload size={18} />
      <span>{file ? file.name : label}</span>
      <input type="file" required={required} onChange={(event) => onChange(event.target.files?.[0] || null)} />
    </label>
  );
}

function Field({ label, value, onChange }) {
  return (
    <label>
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Metric({ label, value, tone = "" }) {
  return (
    <div className={`metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PanelTitle({ icon: Icon, title }) {
  return (
    <div className="panel-title">
      <Icon size={20} />
      <h2>{title}</h2>
    </div>
  );
}

function StatusBadge({ status }) {
  return <span className={`status-badge ${status}`}>{status}</span>;
}

function EmptyState({ text }) {
  return (
    <div className="empty-state">
      <AlertTriangle size={18} />
      <span>{text}</span>
    </div>
  );
}

function labelFor(key) {
  return key
    .split(/[_-]/)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}
function cleanProteinSequence(value) {
  return value
    .split("\n")
    .filter((line) => !line.trim().startsWith(">"))
    .join("")
    .replace(/[^A-Za-z]/g, "")
    .toUpperCase();
}

function AutoDockPanel({ onCreated, onError }) {
  const [protein, setProtein] = useState("");
  const [compound, setCompound] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const job = await runAutoDock(protein, compound);
      onCreated(job);
    } catch (err) {
      onError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="surface full-width">
      <PanelTitle icon={Zap} title="Auto-Docking Workflow" />
      <p className="eyebrow" style={{ marginBottom: '20px' }}>
        Enter names to automatically fetch structures from PubChem/RCSB and predict docking grids.
      </p>

      <form onSubmit={handleSubmit} className="docking-form">
        <div className="form-grid">
          <label>
            Target Protein (Name or PDB ID)
            <input
              placeholder="e.g. Mpro or 7BQY"
              value={protein}
              onChange={e => setProtein(e.target.value)}
              required
            />
          </label>
          <label>
            Ligand (Common Name)
            <input
              placeholder="e.g. Paxlovid or Aspirin"
              value={compound}
              onChange={e => setCompound(e.target.value)}
              required
            />
          </label>
        </div>

        <div style={{ marginTop: '20px' }}>
          <button className="primary-button" disabled={loading || !protein || !compound} type="submit">
            <Zap size={18} />
            <span>{loading ? "Fetching & Preparing..." : "Launch Auto-Dock"}</span>
          </button>
        </div>
      </form>

      <div className="toast" style={{ marginTop: '20px', background: '#1a222d', borderColor: '#252b38', color: '#8b99ad' }}>
        <small>
          <strong>Note:</strong> This workflow uses the protein centroid for the docking grid.
          For specific binding pockets, use Manual Docking.
        </small>
      </div>
    </section>
  );
}
