import {
  AppShell,
  Banner,
  Button,
  Card,
  DropdownMenu,
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
  Activity,
  Layers,
  Radio,
  RefreshCw,
  ScrollText,
  Server,
  UserRound,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { api } from "./api";
import {
  Badge,
  CollectionAvailable,
  CurrentSnapshot,
  systemHealth,
  text,
} from "./components";
import { freshView } from "./freshness";
import { CoreNetworkPage } from "./pages/CoreNetworkPage";
import { DeviceDetailPage, DevicesPage } from "./pages/DevicesPage";
import { EventsPage } from "./pages/EventsPage";
import { GnbPage } from "./pages/GnbPage";
import { OverviewPage } from "./pages/OverviewPage";
import {
  ComponentDetailPage,
  DiagnosticsPage,
  HistoryPage,
  OperationsPage,
} from "./pages/SecondaryPages";
import "./style.css";
import type { Snapshot } from "./types";
import { UIProvider } from "./ui-provider";

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
  return (
    navigation.find(([route]) =>
      route === "/"
        ? path === "/" || path === "/overview"
        : path.startsWith(route),
    )?.[1] || "Overview"
  );
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
  const navigate = useNavigate();
  const stack = "ocudu";
  const snapshot = freshView(rawSnapshot, connected, received.current, now);
  const acceptSnapshot = (next: Snapshot) => {
    received.current = Date.now();
    setNow(received.current);
    setConnected(true);
    setRawSnapshot(next);
  };

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => setMenu(false), [location.pathname]);
  useEffect(() => {
    const expired = () => {
      setCsrf("");
      setRawSnapshot(null);
      setConnected(false);
      setError("Session expired. Sign in again.");
    };
    window.addEventListener("aoc-auth-expired", expired);
    api<{ csrf: string }>("session")
      .then((result) => setCsrf(result.csrf))
      .catch(() => {})
      .finally(() => setReady(true));
    return () => window.removeEventListener("aoc-auth-expired", expired);
  }, []);
  useEffect(() => {
    if (!csrf) return;
    const controller = new AbortController();
    let alive = true;
    api<Snapshot>("snapshot", { signal: controller.signal })
      .then((next) => {
        if (alive) acceptSnapshot(next);
      })
      .catch(() => {});
    const stream = new EventSource("/api/v1/stream");
    stream.addEventListener("snapshot", (event) => {
      if (alive) {
        acceptSnapshot(JSON.parse((event as MessageEvent).data));
        setError("");
      }
    });
    stream.addEventListener("auth_expired", () => {
      stream.close();
      setCsrf("");
      setRawSnapshot(null);
      setConnected(false);
    });
    stream.onerror = () => {
      if (alive) {
        setConnected(false);
        setError("Live connection lost. Reconnecting…");
      }
    };
    const history = window.setInterval(
      () => setRevision((value) => value + 1),
      30000,
    );
    return () => {
      alive = false;
      controller.abort();
      stream.close();
      window.clearInterval(history);
    };
  }, [csrf]);

  async function login(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await api<{ csrf: string }>("login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      setCsrf(result.csrf);
      setPassword("");
      setError("");
    } catch (exc) {
      setError(
        (exc as Error).message === "invalid_credentials"
          ? "Incorrect password"
          : (exc as Error).message,
      );
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    try {
      acceptSnapshot(await api<Snapshot>("snapshot"));
      setRevision((value) => value + 1);
      setError("");
    } catch (exc) {
      setError((exc as Error).message);
    }
  }
  async function logout() {
    try {
      await api("logout", {
        method: "POST",
        headers: { "X-CSRF-Token": csrf },
      });
      setCsrf("");
      setRawSnapshot(null);
      setConnected(false);
    } catch (exc) {
      setError((exc as Error).message);
    }
  }

  if (!ready)
    return (
      <Stack className="login-screen" align="center" justify="center">
        <Spinner label="Loading Agentic-OCUDU" />
      </Stack>
    );
  if (!csrf)
    return (
      <Stack
        className="login-screen"
        align="center"
        justify="center"
        padding={6}
      >
        <Card width="100%" maxWidth={440}>
          <form onSubmit={login}>
            <Stack gap={6}>
              <Text type="label">Agentic-OCUDU · Spark Operations</Text>
              <Heading level={1}>Sign in to Spark</Heading>
              <Text color="secondary">
                Use the administrator password configured for this Agentic-OCUDU
                Spark.
              </Text>
              <TextInput
                label="Administrator password"
                type="password"
                value={password}
                onChange={setPassword}
                autoComplete="current-password"
                isRequired
                hasAutoFocus
              />
              {error && <Banner status="error" title={text(error)} />}
              <Button
                label="Sign in"
                type="submit"
                variant="primary"
                isLoading={busy}
                width="100%"
              />
            </Stack>
          </form>
        </Card>
      </Stack>
    );

  const health = systemHealth(snapshot, snapshot?.active_stack || stack);
  const props = snapshot ? { snapshot, stack, refresh: revision, csrf } : null;
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
                Spark Operations
              </Text>
            </Stack>
          }
          footer={
            <Stack className="system-state" padding={4} gap={2}>
              <Badge state={health.state} />
              <Text type="supporting" color="secondary">
                {health.state === "healthy"
                  ? "All systems normal"
                  : "Attention required"}
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
              isSelected={
                path === "/"
                  ? location.pathname === "/"
                  : location.pathname.startsWith(path)
              }
              onClick={() => setMenu(false)}
            />
          ))}
        </SideNav>
      }
      topNav={
        <TopNav
          label="Spark toolbar"
          heading={<Heading level={1}>{pageTitle(location.pathname)}</Heading>}
          endContent={
            <Stack direction="horizontal" align="center" gap={3}>
              <span className="collection-status">
                <Badge state={snapshot?.collector_status || "unavailable"} />
              </span>
              <Button
                label="Refresh"
                variant="ghost"
                isIconOnly
                icon={<RefreshCw size={18} />}
                onClick={refresh}
              />
              <DropdownMenu
                button={{
                  label: "Account",
                  variant: "ghost",
                  icon: <UserRound size={18} />,
                  isIconOnly: true,
                }}
                alignment="end"
                items={[
                  {
                    label: "Operations",
                    onClick: () => navigate("/operations"),
                  },
                  {
                    label: "Diagnostics",
                    onClick: () => navigate("/diagnostics"),
                  },
                  {
                    label: "Metric history",
                    onClick: () => navigate("/history"),
                  },
                  { type: "divider" },
                  { label: "Sign out", onClick: logout },
                ]}
              />
            </Stack>
          }
        />
      }
    >
      <Stack className="page-content" gap={6}>
        {error && <Banner status="warning" title={text(error)} />}
        {props ? (
          <CollectionAvailable.Provider
            value={snapshot?.collector_status === "ok"}
          >
            <CurrentSnapshot.Provider value={snapshot}>
              <Routes>
                <Route path="/" element={<OverviewPage {...props} />} />
                <Route path="/overview" element={<Navigate to="/" replace />} />
                <Route path="/gnb" element={<GnbPage {...props} />} />
                <Route path="/ran" element={<Navigate to="/gnb" replace />} />
                <Route path="/core" element={<CoreNetworkPage {...props} />} />
                <Route
                  path="/components/:id"
                  element={<ComponentDetailPage {...props} />}
                />
                <Route path="/devices" element={<DevicesPage {...props} />} />
                <Route
                  path="/devices/:id"
                  element={<DeviceDetailPage {...props} />}
                />
                <Route path="/events" element={<EventsPage {...props} />} />
                <Route path="/history" element={<HistoryPage {...props} />} />
                <Route
                  path="/diagnostics"
                  element={<DiagnosticsPage {...props} />}
                />
                <Route
                  path="/operations"
                  element={<OperationsPage {...props} />}
                />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </CurrentSnapshot.Provider>
          </CollectionAvailable.Provider>
        ) : (
          <Spinner label="Loading Spark status" />
        )}
        <Text type="supporting" color="secondary">
          Spark / ARM64 · OCUDU + Open5GS
        </Text>
      </Stack>
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
