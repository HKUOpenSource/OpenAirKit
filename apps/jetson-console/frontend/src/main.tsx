import { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { Activity, Cpu, Gauge, History as HistoryIcon, LayoutDashboard, LogOut, Menu, Radio, Settings as SettingsIcon, SlidersHorizontal, X } from "lucide-react";
import { api, Obj } from "./api";
import { Badge } from "./components";
import { Context, DeviceSetup, History, Overview, Settings, SpeedTest } from "./pages";
import "./style.css";

const navigation = [
  ["/", "Overview", LayoutDashboard], ["/setup", "Device Setup", SlidersHorizontal],
  ["/speed", "Speed Test", Gauge], ["/history", "History", HistoryIcon],
  ["/settings", "Settings", SettingsIcon],
] as const;
const pageTitles: Record<string, string> = { "/": "Network overview", "/setup": "Device Setup", "/speed": "Speed Test", "/history": "History", "/settings": "Settings" };

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(false);
  const [status, setStatus] = useState<Obj>({ quality: "unavailable", health: "unknown", connected: false, layers: [] });
  const [config, setConfig] = useState<Obj>({ network: {} });
  const [jobs, setJobs] = useState<Obj[]>([]);
  const [received, setReceived] = useState(0);
  const [clock, setClock] = useState(Date.now());
  const [streamConnected, setStreamConnected] = useState(false);
  const [pending, setPending] = useState<{ kind: string; params: Obj } | null>(null);
  const [busy, setBusy] = useState(false);
  const location = useLocation();

  const refresh = useCallback(() => {
    Promise.all([api("status"), api("config"), api("jobs")]).then(([nextStatus, nextConfig, nextJobs]) => {
      setStatus(nextStatus); setConfig(nextConfig); setJobs(nextJobs); setReceived(Date.now());
    }).catch(reason => setError(String(reason)));
  }, []);

  useEffect(() => {
    api("auth/session").then(() => setAuthenticated(true)).catch(() => {}).finally(() => setChecking(false));
    const expired = () => setAuthenticated(false);
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    refresh();
    const stream = new EventSource("/api/v1/events/stream");
    stream.addEventListener("status", event => { setStatus(JSON.parse((event as MessageEvent).data)); setReceived(Date.now()); setStreamConnected(true); });
    stream.addEventListener("expired", () => setAuthenticated(false));
    stream.addEventListener("unavailable", () => setStreamConnected(false));
    stream.addEventListener("reconnect", () => setStreamConnected(false));
    stream.onerror = () => setStreamConnected(false);
    const clockTimer = window.setInterval(() => setClock(Date.now()), 1000);
    const jobsTimer = window.setInterval(() => api("jobs").then(setJobs).catch(() => {}), 4000);
    return () => { stream.close(); clearInterval(clockTimer); clearInterval(jobsTimer); };
  }, [authenticated, refresh]);

  const stale = received === 0 || clock - received > 10000 || clock / 1000 - (status.evidence_at || 0) > 20;
  const current = stale ? { ...status, quality: "stale", health: "unknown", connected: false,
    connection_reason: "Live device evidence is stale", radio: {}, data_session: {}, network: {}, probes: {},
    layers: (status.layers || []).map((layer: Obj) => ({ ...layer, state: "unknown", quality: "stale", reason: "Evidence expired" })) } : status;

  function begin(kind: string, params: Obj = {}) {
    if (!config.revision || !status.commissioned || !status.management_verified) {
      setError("Device commissioning and management-route verification must pass before an operation."); return;
    }
    setPending({ kind, params });
  }

  async function confirm() {
    if (!pending) return;
    setBusy(true); setError("");
    try {
      const job = await api("jobs", { kind: pending.kind, revision: config.revision, params: pending.params });
      if (pending.kind !== "setup") await api(`jobs/${job.id}/run`, { confirmed: true });
      setPending(null); refresh();
    } catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }

  const context: Context = { status: current, config, jobs, refresh, error: setError, begin,
    maintenance: () => api("maintenance", { enabled: !status.maintenance }).then(refresh).catch(reason => setError(String(reason))) };

  if (checking) return <div className="login-screen"><Radio /><p>Checking session</p></div>;
  if (!authenticated) return <div className="login-screen"><form onSubmit={async event => {
    event.preventDefault();
    try { await api("auth/login", { password }); setPassword(""); setError(""); setAuthenticated(true); }
    catch (reason) { setError(String(reason)); }
  }}><div className="login-brand"><span><Radio size={21} /></span><b>Agentic-OCUDU</b></div><h1>Jetson Console</h1><p>Sign in to manage the local 5G data connection.</p>
    <label>Password<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required autoFocus /></label>
    {error ? <p className="alert error" role="alert">{error}</p> : null}<button className="primary">Sign in</button></form></div>;

  return <div className="shell"><aside className={menu ? "open" : ""}><div className="brand"><span><Radio size={20} /></span><b>Agentic-OCUDU<small>JETSON CONSOLE</small></b><button className="icon mobile" aria-label="Close navigation" onClick={() => setMenu(false)}><X /></button></div>
    <nav aria-label="Primary navigation">{navigation.map(([path, label, Icon]) => <NavLink key={path} to={path} end={path === "/"} onClick={() => setMenu(false)}><Icon size={18} />{label}</NavLink>)}</nav>
    <div className="system-state"><Activity size={17} /><div><b>{current.connected ? "Data connected" : current.maintenance ? "Maintenance" : "Attention required"}</b><small>{current.connected ? "All checks verified" : "Review current evidence"}</small></div></div></aside>
    {menu ? <button className="scrim" aria-label="Close navigation" onClick={() => setMenu(false)} /> : null}
    <div className="workspace"><header><button className="icon mobile" aria-label="Open navigation" onClick={() => setMenu(true)}><Menu /></button><h1>{pageTitles[location.pathname] || "Jetson Console"}</h1>
      <div className="header-device"><Cpu size={19} /><span>Jetson Orin<small>RM520N-GL</small></span></div><Badge state={streamConnected && !stale ? "live" : "stale"} /><button className="icon" aria-label="Sign out" title="Sign out" onClick={() => api("auth/logout", {}).then(() => setAuthenticated(false))}><LogOut size={18} /></button></header>
      <main>{status.simulation ? <div className="banner">Simulator · hardware operations are disabled</div> : null}{stale ? <div className="banner warning" role="status">Live stream unavailable. Current values are marked stale until new evidence arrives.</div> : null}
        {error ? <div className="banner error" role="alert"><span>{error}</span><button className="icon" aria-label="Dismiss error" onClick={() => setError("")}><X size={15} /></button></div> : null}
        <Routes><Route path="/" element={<Overview {...context} />} /><Route path="/setup" element={<DeviceSetup {...context} />} /><Route path="/speed" element={<SpeedTest {...context} />} /><Route path="/history" element={<History {...context} />} /><Route path="/settings" element={<Settings {...context} />} /><Route path="*" element={<Overview {...context} />} /></Routes>
      </main></div>
    {pending ? <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="confirmation-title"><h2 id="confirmation-title">{pending.kind === "speed" ? "Start speed test?" : pending.kind === "recover" ? "Start recovery?" : "Create setup plan?"}</h2>
      <p>{pending.kind === "speed" ? "The test runs only through the detected RM520N RNDIS route." : "Device operations can briefly interrupt the active data connection."}</p>
      <div className="confirmation"><b>V2 data network</b><span>{config.network?.plmn} · n{config.network?.radio?.band} · {config.network?.data?.dnn} · {config.network?.data?.ue_pool}</span></div>
      <div className="actions"><button disabled={busy} onClick={() => setPending(null)}>Back</button><button className="primary" disabled={busy} onClick={confirm}>{busy ? "Preparing…" : "Confirm"}</button></div></div></div> : null}
  </div>;
}

createRoot(document.getElementById("root")!).render(<BrowserRouter><App /></BrowserRouter>);
