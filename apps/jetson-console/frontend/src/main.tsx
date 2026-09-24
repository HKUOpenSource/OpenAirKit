import {
  AlertDialog,
  AppShell,
  Banner,
  Button,
  Card,
  Heading,
  SideNav,
  SideNavItem,
  Spinner,
  Stack,
  Text,
  TextInput,
  TopNav,
} from "@astryxdesign/core";
import {
  History as HistoryIcon,
  LayoutDashboard,
  LogOut,
  Settings as SettingsIcon,
  SlidersHorizontal,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { api, Obj } from "./api";
import { Badge } from "./components";
import { Context, DeviceSetup, History, Overview, Settings } from "./pages";
import "./style.css";
import { UIProvider } from "./ui-provider";

const navigation = [
  ["/", "Overview", LayoutDashboard],
  ["/setup", "Device Setup", SlidersHorizontal],
  ["/history", "History", HistoryIcon],
  ["/settings", "Settings", SettingsIcon],
] as const;
const pageTitles: Record<string, string> = {
  "/": "Network overview",
  "/setup": "Device Setup",
  "/history": "History",
  "/settings": "Settings",
};

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(false);
  const [status, setStatus] = useState<Obj>({
    quality: "unavailable",
    health: "unknown",
    connected: false,
    layers: [],
  });
  const [config, setConfig] = useState<Obj>({ network: {} });
  const [jobs, setJobs] = useState<Obj[]>([]);
  const [received, setReceived] = useState(0);
  const [clock, setClock] = useState(Date.now());
  const [streamConnected, setStreamConnected] = useState(false);
  const [pending, setPending] = useState<{ kind: string; params: Obj } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const location = useLocation();

  const refresh = useCallback(() => {
    Promise.all([api("status"), api("config"), api("jobs")])
      .then(([nextStatus, nextConfig, nextJobs]) => {
        setStatus(nextStatus);
        setConfig(nextConfig);
        setJobs(nextJobs);
        setReceived(Date.now());
      })
      .catch((reason) => setError(String(reason)));
  }, []);

  useEffect(() => {
    api("auth/session")
      .then(() => setAuthenticated(true))
      .catch(() => {})
      .finally(() => setChecking(false));
    const expired = () => setAuthenticated(false);
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    refresh();
    const stream = new EventSource("/api/v1/events/stream");
    stream.addEventListener("status", (event) => {
      setStatus(JSON.parse((event as MessageEvent).data));
      setReceived(Date.now());
      setStreamConnected(true);
    });
    stream.addEventListener("expired", () => setAuthenticated(false));
    stream.addEventListener("unavailable", () => setStreamConnected(false));
    stream.addEventListener("reconnect", () => setStreamConnected(false));
    stream.onerror = () => setStreamConnected(false);
    const clockTimer = window.setInterval(() => setClock(Date.now()), 1000);
    const jobsTimer = window.setInterval(
      () =>
        api("jobs")
          .then(setJobs)
          .catch(() => {}),
      4000,
    );
    return () => {
      stream.close();
      clearInterval(clockTimer);
      clearInterval(jobsTimer);
    };
  }, [authenticated, refresh]);

  const streamStale = received === 0 || clock - received > 10000;
  const evidenceStale =
    status.quality === "stale" || clock / 1000 - (status.evidence_at || 0) > 20;
  const stale = streamStale || evidenceStale;
  const current = stale
    ? {
        ...status,
        quality: "stale",
        health: "unknown",
        connected: false,
        registered: null,
        data_session_active: null,
        lab_policy_match: null,
        management_protected: null,
        connection_reason: "Live device evidence is stale",
        radio: {},
        data_session: {},
        network: {},
        probes: {},
        layers: (status.layers || []).map((layer: Obj) => ({
          ...layer,
          state: "unknown",
          quality: "stale",
          reason: "Evidence expired",
        })),
      }
    : status;

  function begin(kind: string, params: Obj = {}) {
    if (
      !config.revision ||
      !status.commissioned ||
      !status.management_verified
    ) {
      setError(
        "Device commissioning and management-route verification must pass before an operation.",
      );
      return;
    }
    setPending({ kind, params });
  }

  async function confirm() {
    if (!pending) return;
    setBusy(true);
    setError("");
    try {
      const job = await api("jobs", {
        kind: pending.kind,
        revision: config.revision,
        params: pending.params,
      });
      if (pending.kind !== "setup")
        await api(`jobs/${job.id}/run`, { confirmed: true });
      setPending(null);
      refresh();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  const context: Context = {
    status: current,
    config,
    jobs,
    refresh,
    error: setError,
    begin,
    maintenance: () =>
      api("maintenance", { enabled: !status.maintenance })
        .then(refresh)
        .catch((reason) => setError(String(reason))),
  };

  if (checking)
    return (
      <Stack className="login-screen" align="center" justify="center">
        <Spinner label="Checking session" />
      </Stack>
    );
  if (!authenticated)
    return (
      <Stack
        className="login-screen"
        align="center"
        justify="center"
        padding={6}
      >
        <Card width="100%" maxWidth={440}>
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              try {
                await api("auth/login", { password });
                setPassword("");
                setError("");
                setAuthenticated(true);
              } catch (reason) {
                setError(String(reason));
              } finally {
                setBusy(false);
              }
            }}
          >
            <Stack gap={6}>
              <Text type="label">Agentic-OCUDU</Text>
              <Heading level={1}>Jetson Console</Heading>
              <Text color="secondary">
                Sign in to manage the local 5G data connection.
              </Text>
              <TextInput
                label="Password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={setPassword}
                isRequired
                hasAutoFocus
              />
              {error && <Banner status="error" title={error} />}
              <Button
                label="Sign in"
                variant="primary"
                type="submit"
                isLoading={busy}
                width="100%"
              />
            </Stack>
          </form>
        </Card>
      </Stack>
    );

  return (
    <AppShell
      height="auto"
      variant="section"
      contentPadding={0}
      mobileNav={{ isOpen: menu, onOpenChange: setMenu }}
      sideNav={
        <SideNav
          aria-label="Primary navigation"
          header={
            <Stack padding={4} gap={1}>
              <Text weight="semibold">Agentic-OCUDU</Text>
              <Text type="supporting" color="secondary">
                Jetson Console
              </Text>
            </Stack>
          }
          footer={
            <Stack padding={4} gap={2}>
              <Badge
                state={
                  current.connected
                    ? "connected"
                    : current.maintenance
                      ? "maintenance"
                      : "unknown"
                }
              />
              <Text type="supporting" color="secondary">
                {current.connected
                  ? "All checks verified"
                  : "Review current evidence"}
              </Text>
            </Stack>
          }
        >
          {navigation.map(([path, label, Icon]) => (
            <SideNavItem
              key={path}
              href={path}
              label={label}
              icon={<Icon size={18} />}
              isSelected={location.pathname === path}
              onClick={() => setMenu(false)}
            />
          ))}
        </SideNav>
      }
      topNav={
        <TopNav
          label="Jetson toolbar"
          heading={
            <Heading level={1}>
              {pageTitles[location.pathname] || "Jetson Console"}
            </Heading>
          }
          endContent={
            <Stack direction="horizontal" align="center" gap={3}>
              <Badge state={streamConnected && !stale ? "live" : "stale"} />
              <Button
                label="Sign out"
                variant="ghost"
                isIconOnly
                icon={<LogOut size={18} />}
                onClick={() =>
                  api("auth/logout", {})
                    .then(() => setAuthenticated(false))
                    .catch((reason) => setError(String(reason)))
                }
              />
            </Stack>
          }
        />
      }
    >
      <Stack className="page-content" gap={6}>
        {status.simulation && (
          <Banner
            status="info"
            title="Simulator · hardware operations are disabled"
          />
        )}
        {stale && (
          <Banner
            status="warning"
            title={streamStale
              ? "Live stream unavailable. Current values are marked stale until new evidence arrives."
              : "Device evidence is stale. Waiting for a fresh device sample."}
          />
        )}
        {error && (
          <Banner
            status="error"
            title={error}
            isDismissable
            dismissLabel="Dismiss error"
            onDismiss={() => setError("")}
          />
        )}
        <Routes>
          <Route path="/" element={<Overview {...context} />} />
          <Route path="/setup" element={<DeviceSetup {...context} />} />
          <Route path="/history" element={<History {...context} />} />
          <Route path="/settings" element={<Settings {...context} />} />
          <Route path="*" element={<Overview {...context} />} />
        </Routes>
      </Stack>
      <AlertDialog
        isOpen={Boolean(pending)}
        onOpenChange={(open) => {
          if (!open && !busy) setPending(null);
        }}
        title={
          pending?.kind === "recover" ? "Start recovery?" : "Create setup plan?"
        }
        description={`Device operations can briefly interrupt the active data connection. Network ${config.network?.plmn} · ${config.network?.data?.dnn} · ${config.network?.data?.ue_pool}.`}
        cancelLabel="Back"
        actionLabel="Confirm"
        actionVariant="primary"
        isActionLoading={busy}
        onAction={confirm}
      />
    </AppShell>
  );
}

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <UIProvider>
      <App />
    </UIProvider>
  </BrowserRouter>,
);
