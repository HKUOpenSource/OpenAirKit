import { useEffect, useRef, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { Activity, ChevronDown, Clock, Cpu, Layers, LockKeyhole, LogOut, Menu, Radio, RefreshCw, ScrollText, Server, Settings, ShieldCheck, UserRound, Wrench, X } from "lucide-react";
import { api } from "./api";
import { Badge, CollectionAvailable, CurrentSnapshot, systemHealth, text } from "./components";
import { freshView } from "./freshness";
import { CoreNetworkPage } from "./pages/CoreNetworkPage";
import { DeviceDetailPage, DevicesPage } from "./pages/DevicesPage";
import { EventsPage } from "./pages/EventsPage";
import { GnbPage } from "./pages/GnbPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ComponentDetailPage, DiagnosticsPage, HistoryPage, OperationsPage } from "./pages/SecondaryPages";
import type { Snapshot } from "./types";
import "./style.css";

const navigation = [
  ["/", "Overview", Activity],
  ["/gnb", "gNB", Radio],
  ["/core", "Core Network", Server],
  ["/devices", "Devices", Layers],
  ["/events", "Events", ScrollText],
] as const;

function pageTitle(path: string) {
  if (path.startsWith("/components/")) return "Component details";
  if (path.startsWith("/devices/")) return "Device details";
  if (path === "/history") return "History";
  if (path === "/diagnostics") return "Diagnostics";
  if (path === "/operations") return "Operations";
  return navigation.find(([route]) => route === "/" ? path === "/" || path === "/overview" : path.startsWith(route))?.[1] || "Overview";
}

function App() {
  const [csrf, setCsrf] = useState("");
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [rawSnapshot, setRawSnapshot] = useState<Snapshot | null>(null);
  const [menu, setMenu] = useState(false);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [connected, setConnected] = useState(false);
  const [now, setNow] = useState(Date.now());
  const received = useRef(0);
  const location = useLocation();
  const stack = "ocudu";
  const snapshot = freshView(rawSnapshot, connected, received.current, now);
  const acceptSnapshot = (next: Snapshot) => { received.current = Date.now(); setNow(received.current); setConnected(true); setRawSnapshot(next); };

  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  useEffect(() => setMenu(false), [location.pathname]);
  useEffect(() => {
    const expired = () => { setCsrf(""); setRawSnapshot(null); setConnected(false); setError("Session expired. Sign in again."); };
    window.addEventListener("aoc-auth-expired", expired);
    api<{csrf: string}>("session").then(result => setCsrf(result.csrf)).catch(() => {}).finally(() => setReady(true));
    return () => window.removeEventListener("aoc-auth-expired", expired);
  }, []);
  useEffect(() => {
    if (!csrf) return;
    const controller = new AbortController(); let alive = true;
    api<Snapshot>("snapshot", {signal: controller.signal}).then(next => { if (alive) acceptSnapshot(next); }).catch(() => {});
    const stream = new EventSource("/api/v1/stream");
    stream.addEventListener("snapshot", event => { if (alive) { acceptSnapshot(JSON.parse((event as MessageEvent).data)); setError(""); } });
    stream.addEventListener("auth_expired", () => { stream.close(); setCsrf(""); setRawSnapshot(null); setConnected(false); });
    stream.onerror = () => { if (alive) { setConnected(false); setError("Live connection lost. Reconnecting…"); } };
    const history = window.setInterval(() => setRevision(value => value + 1), 30000);
    return () => { alive = false; controller.abort(); stream.close(); window.clearInterval(history); };
  }, [csrf]);

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try { const result = await api<{csrf: string}>("login", {method: "POST", body: JSON.stringify({password})}); setCsrf(result.csrf); setPassword(""); setError(""); }
    catch (exc) { setError((exc as Error).message === "invalid_credentials" ? "Incorrect password" : (exc as Error).message); }
    finally { setBusy(false); }
  }
  async function refresh() {
    try { acceptSnapshot(await api<Snapshot>("snapshot")); setRevision(value => value + 1); setError(""); }
    catch (exc) { setError((exc as Error).message); }
  }
  async function logout() {
    try { await api("logout", {method: "POST", headers: {"X-CSRF-Token": csrf}}); setCsrf(""); setRawSnapshot(null); setConnected(false); }
    catch (exc) { setError((exc as Error).message); }
  }

  if (!ready) return <div className="boot-screen"><div className="signal-loader" />Loading Agentic-OCUDU</div>;
  if (!csrf) return <div className="login-page">
    <header><div className="brand"><Radio /><span><strong>Agentic-OCUDU</strong><small>Spark Operations</small></span></div><span><ShieldCheck />Independent lab network</span></header>
    <main><form className="login-panel" onSubmit={login}><h1>Sign in to Spark</h1><p>Use the administrator password configured for this Agentic-OCUDU Spark.</p><label htmlFor="password">Administrator password</label><div className="password-field"><LockKeyhole /><input id="password" type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" required autoFocus /></div>{error && <div className="form-error" role="alert">{text(error)}</div>}<button className="primary-button" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button></form></main>
    <footer>OCUDU 5G SA · Spark monitoring</footer>
  </div>;

  const health = systemHealth(snapshot, snapshot?.active_stack || stack);
  const props = snapshot ? {snapshot, stack, refresh: revision, csrf} : null;
  return <div className="app-shell">
    <aside className={`sidebar ${menu ? "is-open" : ""}`}><div className="sidebar-head"><div className="brand"><Radio /><span><strong>Agentic-OCUDU</strong><small>Spark Operations</small></span></div><button className="icon-button mobile-only" aria-label="Close menu" onClick={() => setMenu(false)}><X /></button></div>
      <nav aria-label="Primary navigation">{navigation.map(([path, label, Icon]) => <NavLink key={path} to={path} end={path === "/"} className={({isActive}) => isActive ? "active" : ""}><Icon />{label}</NavLink>)}</nav>
      <div className="system-state"><span className={`status-dot ${health.state}`} /><span><b>System</b><small title={health.reason}>{health.state === "healthy" ? "All systems normal" : "Attention required"}</small></span></div>
    </aside>
    {menu && <button className="sidebar-scrim" aria-label="Close menu overlay" onClick={() => setMenu(false)} />}
    <div className="workspace"><header className="topbar"><button className="icon-button menu-button mobile-only" aria-label="Open menu" onClick={() => setMenu(true)}><Menu /></button><h1>{pageTitle(location.pathname)}</h1>
      <div className="topbar-actions"><div className="device-mark"><Cpu /><span><b>Spark</b><small>Radio &amp; core</small></span></div><span className="collection-status" title="Collector freshness">Collection <Badge state={snapshot?.collector_status || "unavailable"} /></span><button className="icon-button" aria-label="Refresh" onClick={refresh}><RefreshCw /></button>
        <details className="account-menu"><summary className="account-button" aria-label="Account"><UserRound /><span>ops_engineer</span><ChevronDown /></summary><div className="account-options"><small>Local administrator</small><Link to="/operations"><Settings />Operations</Link><Link to="/diagnostics"><Wrench />Diagnostics</Link><Link to="/history"><Clock />Metric history</Link><button onClick={logout}><LogOut />Sign out</button></div></details>
      </div></header>
      <main>{error && <div className="connection-banner" role="alert">{text(error)}</div>}{props ? <CollectionAvailable.Provider value={snapshot?.collector_status === "ok"}><CurrentSnapshot.Provider value={snapshot}><Routes>
        <Route path="/" element={<OverviewPage {...props} />} /><Route path="/overview" element={<Navigate to="/" replace />} /><Route path="/gnb" element={<GnbPage {...props} />} /><Route path="/ran" element={<Navigate to="/gnb" replace />} />
        <Route path="/core" element={<CoreNetworkPage {...props} />} /><Route path="/components/:id" element={<ComponentDetailPage {...props} />} /><Route path="/devices" element={<DevicesPage {...props} />} /><Route path="/devices/:id" element={<DeviceDetailPage {...props} />} />
        <Route path="/events" element={<EventsPage {...props} />} /><Route path="/history" element={<HistoryPage {...props} />} /><Route path="/diagnostics" element={<DiagnosticsPage {...props} />} /><Route path="/operations" element={<OperationsPage {...props} />} /><Route path="*" element={<Navigate to="/" replace />} />
      </Routes></CurrentSnapshot.Provider></CollectionAvailable.Provider> : <div className="page-loading"><div className="signal-loader" />Loading Spark status</div>}<footer className="app-footer"><ShieldCheck />Spark / ARM64</footer></main>
    </div>
  </div>;
}

createRoot(document.getElementById("root")!).render(<BrowserRouter><App /></BrowserRouter>);
