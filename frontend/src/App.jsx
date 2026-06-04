import React, { useCallback, useEffect, useRef, useState } from "react";
import * as $3Dmol from "3dmol";
import {
  Activity,
  AlertTriangle,
  Beaker,
  CreditCard,
  Database,
  Download,
  Eye,
  FileText,
  FlaskConical,
  LogOut,
  Play,
  RefreshCw,
  ShieldCheck,
  Upload,
  UserPlus,
} from "lucide-react";

import {
  createCheckout,
  createDockingJob,
  downloadFile,
  getFileText,
  getJob,
  getToken,
  health,
  listJobs,
  login,
  me,
  register,
  runAdmet,
  setToken,
} from "./api";

const terminalStates = new Set(["completed", "failed", "canceled"]);

const navItems = [
  ["dashboard", Activity, "Dashboard"],
  ["docking", FlaskConical, "Docking"],
  ["viewer", Eye, "3D Viewer"],
  ["admet", Beaker, "ADMET"],
  ["jobs", Database, "Jobs"],
  ["billing", CreditCard, "Billing"],
];

export default function App() {
  const [user, setUser] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [active, setActive] = useState("dashboard");
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

  if (busy) return <div className="boot">Starting MoliDock Pro</div>;
  if (!user) return <AuthScreen onAuth={handleAuth} health={systemHealth} />;

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
            <p className="eyebrow">Automated molecular docking system</p>
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

        {active === "docking" && (
          <DockingPanel
            onCreated={(job) => {
              setSelectedJob(job);
              setJobs((current) => [job, ...current]);
              setActive("viewer");
              setMessage("Docking job queued");
            }}
            onError={setMessage}
          />
        )}

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

function AuthScreen({ onAuth, health: systemHealth }) {
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
            <span>Docking SaaS console</span>
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

      <section className="system-panel">
        <h2>System</h2>
        <HealthGrid health={systemHealth} />
      </section>
    </main>
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
      const response = await fetch(
        `http://127.0.0.1:8010/admet/compound?name=${encodeURIComponent(compound)}`
      );

      if (!response.ok) {
        throw new Error("ADMET prediction failed");
      }

      const data = await response.json();
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
    .split("_")
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}