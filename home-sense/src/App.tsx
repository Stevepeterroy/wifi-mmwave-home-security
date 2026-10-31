import WifiDevices from "./WifiDevices";
import {recentRadarMapPoints, RADAR_MAP_ECHO_SECONDS} from "./radarMapPreview";
import {motionIndicator} from "./motionIndicator";
import EventPlayback from "./EventPlayback";
import { connectionCounts } from "./connectionCounts";
import EmailSetup from "./EmailSetup";
import EspSetup from "./EspSetup";
import SensorNameEditor from "./SensorNameEditor";
import { renameSensor } from "./moduleNames";
import RouterOverlay from "./RouterOverlay";
import { placeRouter, visibleRouter, storedRouter, updateRouter } from "./routerPlacement";
import { resolveUrl, isAndroid, getServerUrl, setServerUrl, DEFAULT_SERVER_URL } from "./serverConfig";
import ServerSetup from "./ServerSetup";
import { roomPath } from "./roomBoundary";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  Home,
  Layers,
  Radio,
  Shield,
  Settings,
  Plus,
  ArrowUpRight,
  Play,
  Pause,
  ChevronLeft,
  Check,
  Bell,
  Download,
  Upload,
  MapPin,
  Activity,
  Wifi,
  LogOut,
} from "lucide-react";
import { enableBackgroundPush, disableBackgroundPush } from "./push";
import { RoomGesture } from "./roomGesture";
import { planViewBox, homePlanBounds, scanRooms } from "./planProjection";
import { useScanFootprint } from "./useScanFootprint";
import SessionLibrary from "./SessionLibrary";
import RadarDirection from "./RadarDirection";
import RoomDrawing from "./RoomDrawing";
import { placeModule, removeModulePlacement, scanModules, syncScanEnvelope } from "./planPlacement";
import { roomSceneContext } from "./roomScene";
const Scene = lazy(() => import("./Scene"));
import {
  initialConfig,
  transform,
  clusters,
  Tracker,
  MultiTracker,
  TRACK_CURRENT_SECONDS,
  TRACK_DISPLAY_SECONDS,
  isCurrentTrack,
  inRoom,
  withinPlan,
} from "./domain";
import type { Config, Room, Frame, Track, Event } from "./domain";
import {
  deleteSharedModel,
  saveSharedModel as saveModel,
  listSharedModels as listModels,
  uid,
} from "./assets";
import type { ModelAsset } from "./assets";
type SyncRecord = {
  trialId: string;
  provider: "tasks" | "calendar";
  state: "pending" | "failed" | "synced";
  at: number;
  trialStatus: string;
  start: string;
  days: number;
  error?: string;
};
type Live = {
  connected: boolean;
  transport_online?: boolean;
  radar_verified: boolean;
  version: string;
  message: string;
  port: string;
  transport?: "usb" | "wifi";
  csi?: {connected:boolean;samples:number;dropped?:number;rssi?:number;channel?:number;approx_rate?:number;motion?:{status:string;remaining_seconds?:number}};
  radar_uart?: {bytes:number;retained_bytes:number;dropped_bytes:number;sequence_gaps:number;decoded:boolean;complete_point_cloud:boolean};
  motionEvidence?: {status:string};
  activityEstimate?: {enabled:boolean;status:string;label?:string;model_vote?:number;branch?:string};
  ports: { port: string; name: string }[];
  frames: Frame[];
  last_frame: Frame | null;
  now: number;
  scan_running: boolean;
  scan_pending: boolean;
  monitoring?: boolean;
  scan_cycles?: number;
  scan_error?: string;
  status?: { control_errors?: number; data_bytes?: number };
  stop_acknowledged?: boolean | null;
  logs: string[];
  events?: Event[];
  nodes?: Record<string, Live>;
};
const number = (value: FormDataEntryValue | null, fallback = 0) =>
  Number(value ?? fallback);
async function api(path: string, body?: unknown) {
  const r = await fetch(
    resolveUrl(path),
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(path === "/api/home" ? {...(body as Config), events: (body as Config).events.map(e => ({id:e.id, acknowledged:e.acknowledged}))} : body),
        },
  );
  const j = await r.json();
  if (!r.ok) throw Error(j.error || "Request failed");
  return j;
}
function exportFile(data: string, name: string, type = "application/json") {
  const u = URL.createObjectURL(new Blob([data], { type })),
    a = document.createElement("a");
  a.href = u;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
export default function App() {
  const roomGesture = useRef(new RoomGesture());
  useEffect(() => () => roomGesture.current.cancel(), []);

  const [cfg, setCfg] = useState<Config>(initialConfig),
    [loaded, setLoaded] = useState(false),
    [page, setPage] = useState("home"),
    [mode, setMode] = useState<"recorded" | "live">("live"),
    [capture, setCapture] = useState<{ frames: Frame[] } | null>(null),
    [index, setIndex] = useState(0),
    [playing, setPlaying] = useState(true),
    [liveAggregate, setLive] = useState<Live | null>(null),
    [syncRecords, setSyncRecords] = useState<SyncRecord[]>([]),
    [pushStatus, setPushStatus] = useState<{
      configured: boolean;
      enrolled: boolean;
      devices: number;
      states: Record<string, number>;
    } | null>(null),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [motionAlert, setMotionAlert] = useState<Event | null>(null),
    [selected, setSelected] = useState<string | null>(null),
    [hover, setHover] = useState<string | null>(null),
    [tracks, setTracks] = useState<Track[]>([]),
    [models, setModels] = useState<ModelAsset[]>([]),
    [scan, setScan] = useState<ModelAsset>(),
    [dialog, setDialog] = useState<"room" | "module" | null>(null),
    [placing, setPlacing] = useState<string | null>(null),
    [placingRouter, setPlacingRouter] = useState(false),
    [editingSensor, setEditingSensor] = useState<string | null>(null),
    [port, setPort] = useState(""),
    [capabilities, setCapabilities] = useState<{
      google_calendar_configured: boolean;
      google_tasks_configured: boolean;
      polycam_api_configured: boolean;
    } | null>(null),
    [polyCaptures, setPolyCaptures] = useState<{ id: string; name: string }[]>(
      [],
    );
  const [authStatus, setAuthStatus] = useState<{
      enrolled: boolean;
      authenticated: boolean;
      remote: boolean;
    } | null>(null),
    [authRequired, setAuthRequired] = useState(false),
    [authEnrolling, setAuthEnrolling] = useState(false);
  const [wifiKey, setWifiKey] = useState<{
    moduleId: string;
    token: string;
  } | null>(null);
  const [wifiPairing, setWifiPairing] = useState(false);
  const [showServerSetup, setShowServerSetup] = useState(false);
  const [sessionRevision, setSessionRevision] = useState(0);
  const [sessionSaving, setSessionSaving] = useState(false);
  const [reviewLastScan, setReviewLastScan] = useState(false);
  const scanState = useScanFootprint(scan);
  const footprint = scanState?.footprint;
  const bounds = useMemo(
    () => homePlanBounds(cfg.rooms, footprint),
    [cfg.rooms, footprint],
  );
  const mappedRooms = useMemo(
    () =>
      scan
        ? footprint
          ? scanRooms(cfg.rooms, scan.id, bounds)
          : []
        : cfg.rooms,
    [cfg.rooms, scan, footprint, bounds],
  );
  const scanArea = useMemo<Room | undefined>(
    () =>
      scan && footprint
        ? {
            id: "scan:" + scan.id,
            name: "Scanned space",
            x: 0,
            z: 0,
            width: footprint.width,
            depth: footprint.depth,
            care: false,
            modelId: scan.id,
          }
        : undefined,
    [scan, footprint],
  );
  const planRooms = useMemo(
    () => (mappedRooms.length ? mappedRooms : scanArea ? [scanArea] : []),
    [mappedRooms, scanArea],
  );
  const planModules = useMemo(
    () =>
      scan
        ? footprint
          ? scanModules(cfg.modules, cfg.rooms, scan, footprint)
          : []
        : cfg.modules,
    [cfg.modules, cfg.rooms, scan, footprint],
  );
  useEffect(() => {
    if (!scan || !footprint) return;
    setCfg((c) => {
      const rooms = syncScanEnvelope(c.rooms, scan, footprint);
      return rooms === c.rooms ? c : { ...c, rooms };
    });
  }, [scan, footprint]);
  useEffect(() => setWifiKey(null), [cfg.activeModuleId, authRequired]);
  const seenLiveEvents = useRef<Set<string> | null>(null);
  const multiTracker = useRef(new MultiTracker());
  const tracker = useRef(new Tracker()),
    lastFrame = useRef(""),
    awayCount = useRef(0),
    latched = useRef(false),
    configRef = useRef(cfg),
    notificationTimes = useRef<Record<string, number>>({});
  configRef.current = cfg;
  useEffect(() => {
    let active = true;
    api("/api/auth/status")
      .then((status) => {
        if (!active) return null;
        setAuthStatus(status);
        if (status.enrolled && !status.authenticated) {
          setAuthRequired(true);
          return null;
        }
        return Promise.all([
          api("/api/home"),
          api("/api/replay"),
          listModels(),
          api("/api/capabilities"),
        ]);
      })
      .then((result) => {
        if (!result) return;
        const [home, data, assets, caps] = result;
        if (!active) return;
        setCfg(home || initialConfig);
        setMode("live");
        if (home?.dataSource === "recorded") {
          setCfg({...home, dataSource: "live", away: false});
        }
        setCapture(data);
        setModels(assets);
        setScan(
          assets.find((a: ModelAsset) => a.id === home?.homeModelId) ||
            assets[0],
        );
        setCapabilities(caps);
        setPort(
          home?.modules?.find(
            (m: Config["modules"][number]) => m.id === home?.activeModuleId,
          )?.port ||
            home?.modules?.[0]?.port ||
            "",
        );
        setLoaded(true);
      })
      .catch((e) => setError("Could not load local service: " + e.message));
    const poll = () =>
      api("/api/state")
        .then((v) => {
          if (active) {
            setLive(v);
            if (v.syncRecords) setSyncRecords(v.syncRecords);
            if (v.pushStatus) setPushStatus(v.pushStatus);
            if (v.events) {
              if (seenLiveEvents.current)
                for (const event of v.events) {
                  if (
                    event.source === "live" &&
                    !seenLiveEvents.current.has(event.id)
                  ) {
                    setMotionAlert(event);
                    if ("Notification" in window && Notification.permission === "granted")
                    new Notification("Haven: movement detected", {
                      body:
                        event.room +
                        ": radar reflections detected. Person identity is unverified.",
                    });
                  }
                }
              seenLiveEvents.current = new Set(
                v.events.map((e: Event) => e.id),
              );
            }
            if (v.events)
              setCfg((c) => {
                const merged = new Map(c.events.map((e) => [e.id, e]));
                for (const event of v.events)
                  merged.set(event.id, {
                    ...event,
                    acknowledged:
                      event.acknowledged ||
                      merged.get(event.id)?.acknowledged ||
                      false,
                  });
                const events = (v.events as Event[]).map(event => merged.get(event.id)!)
                  .sort((a, b) => b.at.localeCompare(a.at))
                  .slice(0, 200);
                return JSON.stringify(events) === JSON.stringify(c.events)
                  ? c
                  : { ...c, events };
              });
          }
        })
        .catch(() => {
          if (active) setLive(null);
        });
    poll();
    const t = setInterval(poll, 500);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, []);
  useEffect(() => {
    if (!loaded) return;
    const t = setTimeout(
      () =>
        api("/api/home", cfg).catch((e) =>
          setError("Changes could not be saved: " + e.message),
        ),
      350,
    );
    return () => clearTimeout(t);
  }, [cfg, loaded]);
  useEffect(() => {
    if (mode !== "recorded" || !playing || !capture) return;
    const t = setInterval(
      () => setIndex((i) => (i + 1) % capture.frames.length),
      200,
    );
    return () => clearInterval(t);
  }, [mode, playing, capture]);
  const [scanDeleteId, setScanDeleteId] = useState<string | null>(null);
  const [scanDeleteBusy, setScanDeleteBusy] = useState(false);
  const [scanDeleteError, setScanDeleteError] = useState("");
  const [wifiNavigationPending, setWifiNavigationPending] = useState(false);
  useEffect(() => {
    if (page !== "sensors" || !wifiNavigationPending) return;
    const section = document.getElementById("radar-wifi-connection");
    section?.scrollIntoView({behavior: "smooth", block: "start"});
    section?.focus({preventScroll: true});
    setWifiNavigationPending(false);
  }, [page, wifiNavigationPending]);
  const module =
    cfg.modules.find((m) => m.id === cfg.activeModuleId) || cfg.modules[0];
  useEffect(() => {
    const available = liveAggregate?.ports?.map((item) => item.port) || [];
    if (!available.length) { if (port) setPort(""); return; }
    if (!available.includes(port)) setPort(available[0]);
  }, [liveAggregate?.ports, port]);
  const live: Live | null = liveAggregate
    ? {
        ...liveAggregate,
        ...((module && liveAggregate.nodes?.[module.id]) || {
          connected: false,
          radar_verified: false,
          last_frame: null,
          frames: [],
          scan_running: false,
          scan_pending: false,
          logs: [],
          message: "This module is not connected",
        }),
      }
    : null;
  const freshNode = (id: string) => {
    const node = liveAggregate?.nodes?.[id];
    return (
      !!node?.connected &&
      node.radar_verified &&
      !!node.last_frame &&
      liveAggregate!.now - (node.last_frame.received_at || 0) < 1.5
    );
  };
  const anyFresh =
    mode === "recorded" ? !!capture : cfg.modules.some((m) => freshNode(m.id));
  const lastScanFrame = module && !live?.scan_running && (live?.scan_cycles || 0) > 0
    ? [...(liveAggregate?.nodes?.[module.id]?.frames || [])].reverse().find((f) => f.points.length > 0)
    : undefined;
  const showingScanSnapshot = mode === "live" && reviewLastScan && !!lastScanFrame;
  const roomHasEvidence = (r: Room) =>
    mode === "recorded"
      ? !!frame &&
        !!module &&
        planModules.some((m) => m.id === module.id) &&
        (scan ? inRoom(module, r) : module.roomId === r.id)
      : planModules.some(
          (m) => (scan ? inRoom(m, r) : m.roomId === r.id) && freshNode(m.id),
        );
  const frame =
    mode === "recorded"
      ? capture?.frames[index]
      : showingScanSnapshot
        ? lastScanFrame
        : live?.connected &&
          live.radar_verified &&
          live.last_frame &&
          live.now - (live.last_frame.received_at || 0) < 1.5
        ? live.last_frame
        : null;
  const points =
    mode === "recorded"
      ? frame && module && planModules.some((m) => m.id === module.id)
        ? frame.points.map((p) => transform(p, module)).filter((p) => withinPlan(p, bounds))
        : []
      : showingScanSnapshot && module
        ? lastScanFrame.points.map((p) => transform(p, module)).filter((p) => withinPlan(p, bounds))
        : planModules.flatMap((m) =>
          freshNode(m.id)
            ? liveAggregate!.nodes![m.id].last_frame!.points.map((p) =>
                transform(p, m),
              ).filter((p) => withinPlan(p, bounds))
            : [],
        );
  const mapRadarPoints = mode === "live" && !showingScanSnapshot
    ? recentRadarMapPoints(planModules, liveAggregate?.nodes || {}, liveAggregate?.now || Date.now() / 1000, bounds)
    : points.map((point) => ({point, ageSeconds: 0}));
  useEffect(() => {
    if (mode === "live") {
      setTracks(
        multiTracker.current.update(
          planModules,
          liveAggregate?.nodes || {},
          liveAggregate?.now || Date.now() / 1000,
          bounds,
        ),
      );
      return;
    }
    const key = frame
      ? `${mode}:${frame.sequence}:${frame.received_at || 0}`
      : "";
    if (!frame || !module || !planModules.some((m) => m.id === module.id)) {
      tracker.current.reset();
      setTracks([]);
      lastFrame.current = "";
      awayCount.current = 0;
      return;
    }
    if (key === lastFrame.current) return;
    lastFrame.current = key;
    const time =
      mode === "recorded" ? frame.sequence * 0.2 : frame.received_at || 0;
    const next = tracker.current.update(
      clusters(frame.points.map((p) => transform(p, module)).filter((p) => withinPlan(p, bounds))),
      time,
    );
    setTracks(next);
    const motion =
      frame.reported_points > 0 &&
      frame.points.some((p) => Math.abs(p.velocity_cm_s) >= 50);
    awayCount.current = motion ? awayCount.current + 1 : 0;
    if (!motion) latched.current = false;
    if (
      mode === "recorded" &&
      configRef.current.away &&
      awayCount.current >= 3 &&
      !latched.current
    ) {
      latched.current = true;
      const room =
        cfg.rooms.find((r) => r.id === module.roomId)?.name ||
        "Unassigned room";
      const event: Event = {
        id: uid(),
        at: new Date().toISOString(),
        room,
        kind: "Motion reflections while away — review needed",
        source: mode,
        acknowledged: false,
      };
      setCfg((c) => ({ ...c, events: [event, ...c.events].slice(0, 200) }));
    }
  }, [frame, module, mode, cfg.rooms, planModules, liveAggregate, bounds]);
  useEffect(() => {
    tracker.current.reset();
    lastFrame.current = "";
    latched.current = false;
    awayCount.current = 0;
    setTracks([]);
  }, [mode, module]);
  useEffect(() => {
    multiTracker.current.reset();
  }, [mode]);
  async function action(path: string, body: unknown = {}) {
    setError("");
    try {
      const result = await api(path, body);
      if (result.sync) {
        setSyncRecords((records) => [
          ...records.filter(
            (record) =>
              record.trialId !== result.sync.trialId ||
              record.provider !== result.sync.provider,
          ),
          result.sync,
        ]);
        setMessage(
          "Sync confirmed. Review the trial’s integration status for this attempt.",
        );
      } else
        setMessage("Request sent. Check the sensor status for confirmation.");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const currentTracks = mode === "recorded" ? tracks : tracks.filter((t) => isCurrentTrack(t, liveAggregate?.now || Date.now() / 1000));
  const room = planRooms.find((r) => r.id === selected),
    hoverRoom = planRooms.find((r) => r.id === hover),
    roomTracks = (r: Room) => currentTracks.filter((t) => inRoom(t, r)),
    maxX = bounds.width,
    maxZ = bounds.depth;
  const spatialContext = useMemo(
    () =>
      room ? roomSceneContext(room, planModules, models, scan) : undefined,
    [room, planModules, models, scan],
  );
  function changeMode(next: "recorded" | "live") {
    setMode(next);
    setCfg((c) => ({ ...c, away: false, dataSource: next }));
    setMessage("Away mode disarmed when the data source changed.");
    setSelected(null);
  }
  async function importScan(files: FileList | null) {
    if (!files?.length) return;
    setError("");
    try {
      if ([...files].reduce((n, f) => n + f.size, 0) > 150 * 1024 * 1024)
        throw Error("Choose a scan below 150 MB");
      if (![...files].some((f) => /\.(glb|gltf|obj)$/i.test(f.name)))
        throw Error("Choose a GLB, GLTF, or OBJ model");
      const model: ModelAsset = {
        id: uid(),
        name: [...files].find((f) => /\.(glb|gltf|obj)$/i.test(f.name))!.name,
        files: await Promise.all(
          [...files].map(async (f) => ({
            name: f.name,
            data: await f.arrayBuffer(),
          })),
        ),
        scale: 1,
        created: new Date().toISOString(),
      };
      await saveModel(model);
      // Keep the successful upload available even if refreshing the library fails.
      setModels((current) => [...current.filter((m) => m.id !== model.id), model]);
      await activateScan(model);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function activateScan(model: ModelAsset) {
    setError("");
    try {
      const next = { ...configRef.current, homeModelId: model.id };
      await api("/api/home", next);
      setCfg(next);
      setScan(model);
      setSelected(null);
      setMessage(`${model.name} is now your scanned space. Set its room boundaries and radar placement in Setup.`);
    } catch (error) {
      setError("Scan uploaded, but could not set the scanned space: " + (error as Error).message);
    }
  }
  async function updateScan(changes: Partial<ModelAsset>) {
    if (!scan) return;
    const next = { ...scan, ...changes };
    try {
      await saveModel(next);
      setModels(await listModels());
      setScan(next);
    } catch (error) {
      setError((error as Error).message);
    }
  }
  function submitRoom(form: HTMLFormElement) {
    const f = new FormData(form);
    const r: Room = {
      id: uid(),
      name: String(f.get("name")),
      x: number(f.get("x")),
      z: number(f.get("z")),
      width: number(f.get("width"), 4),
      depth: number(f.get("depth"), 4),
      care: false,
      planModelId: scan?.id,
    };
    setCfg((c) => ({ ...c, rooms: [...c.rooms, r] }));
    setDialog(null);
  }
  function submitModule(form: HTMLFormElement) {
    const f = new FormData(form);
    const m = {
      id: uid(),
      name: String(f.get("name")),
      roomId: scan ? "" : String(f.get("room")),
      x: number(f.get("x")),
      z: number(f.get("z")),
      height: number(f.get("height"), 1.2),
      yaw: number(f.get("yaw")),
      fov: 120,
      port: String(f.get("port")),
    };
    setCfg((c) => ({ ...c, modules: [...c.modules, m], activeModuleId: m.id }));
    if (scan) {
      setPlacing(m.id);
      setPage("setup");
      setMessage(
        "Module added. Tap its installed position on the scan to assign its room.",
      );
    }
    setDialog(null);
  }
  const nav = [
    ["home", "Overview", Home],
    ["sensors", "Sensors", Radio],
    ["events", "Activity log", Activity],
    ["setup", "Setup", Settings],
  ] as const;
  if (authRequired || authEnrolling)
    return (
      <div className="loading">
        <Home />
        <h1>{authEnrolling ? "Secure your workspace" : "Welcome back."}</h1>
        <form
          className="auth-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setError("");
            const f = new FormData(e.currentTarget),
              password = String(f.get("password"));
            if (authEnrolling && password !== f.get("confirmation")) {
              setError("Passwords do not match");
              return;
            }
            try {
              await api(authEnrolling ? "/api/auth/setup" : "/api/auth/login", {
                password,
              });
              window.location.reload();
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          <label>
            Workspace password
            <input
              name="password"
              type="password"
              autoComplete={authEnrolling ? "new-password" : "current-password"}
              minLength={authEnrolling ? 12 : undefined}
              maxLength={128}
              required
            />
          </label>
          {authEnrolling && (
            <label>
              Confirm password
              <input
                name="confirmation"
                type="password"
                autoComplete="new-password"
                required
              />
            </label>
          )}
          <button className="primary">
            {authEnrolling ? "Create sign-in" : "Sign in"}
          </button>
          {authEnrolling && (
            <button type="button" onClick={() => setAuthEnrolling(false)}>
              Cancel
            </button>
          )}
          <p role="alert">{error}</p>
          <p className="muted small">
            {authEnrolling
              ? "Choose your own password. It is hashed locally; no preset password is created."
              : "Sign in to access your home scans, sensor settings and events."}
          </p>
        </form>
      </div>
    );
  if (!loaded)
    return (
      <div className="loading">
        <Home />
        <h1>Haven</h1>
        <p>{error || "Opening your home…"}</p>
      </div>
    );
  return (
    <div className="shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("home");
          }}
        >
          <div className="brand-icon">
            <Home size={22} />
          </div>
          haven<span>HOME SENSING</span>
        </a>
        <div className="home-switch">
          <span className="tiny">YOUR SPACE</span>
          <strong>{cfg.homeName}</strong>
          <span className="muted">Local workspace</span>
        </div>
        <nav>
          {nav.map(([id, label, Icon]) => (
            <button
              key={id}
              className={page === id ? "nav active" : "nav"}
              onClick={() => {
                setPage(id);
                setSelected(null);
              }}
            >
              <Icon size={18} />
              {label}
              {id === "events" && cfg.events.some((e) => !e.acknowledged) && (
                <i />
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span
            className={
              "status-dot " +
              (mode === "live" && live?.radar_verified ? "green" : "")
            }
          />
          {mode === "recorded" ? "Recorded data" : "Live sensor preview"}
          <p>
            Privacy starts at home.
            <br />
            Your scans stay in this workspace.
          </p>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <div className="breadcrumb">
              {cfg.homeName} <span>/</span>{" "}
              {room ? room.name : nav.find((n) => n[0] === page)?.[1]}
            </div>
            <h1>
              {room
                ? room.name
                : page === "home"
                  ? "Home sensing overview"
                  : nav.find((n) => n[0] === page)?.[1]}
            </h1>
            <p className="muted">
              {page === "home"
                ? "Live sensor signals and your mapped space."
                : page === "setup"
                  ? "Make the space yours. Place rooms, scans and sensors."
                  : page === "sensors"
                    ? "Connect devices and check live readings."
                    : page === "events"
                      ? "Review saved motion events."
                      : "Manage your home setup."}
            </p>
          </div>
          <div className="header-actions">
            {authStatus?.authenticated && (
              <button
                aria-label="Sign out"
                className="icon-btn"
                onClick={async () => {
                  await api("/api/auth/logout", {});
                  window.location.reload();
                }}
              >
                <LogOut size={17} />
              </button>
            )}
            <button
              className="icon-btn"
              aria-label="Enable desktop alerts"
              onClick={async () => {
                if (!("Notification" in window)) {
                  setError(
                    "Desktop notifications are unavailable in this browser.",
                  );
                  return;
                }
                const p = await Notification.requestPermission();
                setMessage(
                  p === "granted"
                    ? "Desktop alerts enabled while Haven is open."
                    : "Desktop alerts are not enabled.",
                );
              }}
            >
              <Bell size={18} />
            </button>
            <span className="avatar">
              {(cfg.profile || "H")[0].toUpperCase()}
            </span>
          </div>
        </header>
        {!cfg.profile && (
          <section className="welcome">
            <div>
              <strong>Welcome home.</strong>
              <p>
                Name this local workspace to begin. No cloud account is
                required.
              </p>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                setCfg((c) => ({
                  ...c,
                  profile: String(f.get("profile")),
                  homeName: String(f.get("home")),
                }));
                setPage("setup");
              }}
            >
              <input
                name="profile"
                placeholder="Your name"
                aria-label="Your name"
                required
                maxLength={60}
              />
              <input
                name="home"
                placeholder="Home name"
                aria-label="Home name"
                defaultValue="My home"
                required
                maxLength={60}
              />
              <button className="primary">
                Get started <ArrowUpRight size={16} />
              </button>
            </form>
          </section>
        )}
        {error && (
          <div role="alert" className="notice error">
            <span>{error}</span>
            <div style={{ display: "flex", gap: "0.5rem", marginLeft: "auto" }}>
              {isAndroid() && (
                <button
                  type="button"
                  style={{ background: "#4ecda4", color: "#0d1f1c", fontWeight: "bold" }}
                  onClick={() => setShowServerSetup(true)}
                >
                  Change Server
                </button>
              )}
              <button type="button" onClick={() => setError("")}>Dismiss</button>
            </div>
          </div>
        )}
        {message && (
          <div role="status" className="notice">
            {message}
            <button onClick={() => setMessage("")}>Dismiss</button>
          </div>
        )}
        {motionAlert && (
          <aside className="motion-popup" role="alert" aria-live="assertive">
            <strong>Movement detected while Away</strong>
            <p>{motionAlert.room}: moving radar reflections detected.</p>
            <div className="button-row">
              <button onClick={() => { setPage("events"); setSelected(null); setMotionAlert(null); }}>View activity</button>
              <button onClick={() => setMotionAlert(null)}>Dismiss</button>
            </div>
          </aside>
        )}
        <div className="source-strip" role="status" aria-label="Device connections">
          <div>
            <span className={"status-dot " + (liveAggregate && connectionCounts(cfg.modules.map(m => m.id), liveAggregate.nodes).esps > 0 ? "green" : "")} />
            <strong>{liveAggregate
              ? `${connectionCounts(cfg.modules.map(m => m.id), liveAggregate.nodes).esps} ${connectionCounts(cfg.modules.map(m => m.id), liveAggregate.nodes).esps === 1 ? "ESP" : "ESPs"} connected · ${connectionCounts(cfg.modules.map(m => m.id), liveAggregate.nodes).radars} ${connectionCounts(cfg.modules.map(m => m.id), liveAggregate.nodes).radars === 1 ? "radar" : "radars"} verified`
              : "Connection status unavailable"}</strong>
            <span>{liveAggregate
              ? `Across ${cfg.modules.length} sensors. Connected means Haven is receiving data; verified means the radar answered a check.`
              : "Haven is offline. Restart the local service to see live devices."}</span>
          </div>
        </div>
        {page === "home" && !room && (
          <>
            <div className="button-row">
              <button disabled={!live?.radar_verified} onClick={async () => {
                changeMode("live");
                await action("/api/monitoring", {moduleId: module?.id, enabled: !live?.monitoring});
              }}>{live?.monitoring ? "Stop live monitoring" : "Start live monitoring"}</button>
              <span className="muted small">{live?.scan_running
                ? "Live radar readings update the counters below."
                : live?.monitoring || live?.scan_pending ? "Preparing the next radar scan; counters wait for fresh readings."
                : "Monitoring is stopped. Start it to show fresh coordinates and reflection groups."}</span>
            </div>
            {mode === "live" && lastScanFrame && !live?.scan_running && (
              <div className="button-row">
                <button onClick={() => setReviewLastScan((value) => !value)}>{showingScanSnapshot ? "Hide last scan snapshot" : "Show last scan snapshot"}</button>
                <span className="muted small">{showingScanSnapshot ? "Historical PB0 console preview—not live tracking or a complete point cloud." : `${lastScanFrame.points.length} preview coordinates in the last non-empty report.`}</span>
              </div>
            )}
            {mode === "live" && ((live?.status?.control_errors || 0) > 0 || live?.stop_acknowledged === false) && (
              <div className="panel" role="alert">
                <strong>Radar connection needs attention</strong>
                <p>The ESP has reported {live?.status?.control_errors || 0} cumulative UART errors{live?.stop_acknowledged === false ? " and the radar did not acknowledge stop" : ""}. Garbled or missing reports can make positions unreliable. Check the radar wiring and power, then reconnect before monitoring.</p>
              </div>
            )}
            {mode === "live" && live?.scan_error && (
              <div className="panel" role="alert">
                <strong>No radar points: scan setup failed</strong>
                <p>{live.scan_error}. The ESP and radar can be connected and version-verified without delivering a valid point report. Haven will not draw coordinates from unparsed UART bytes or CSI samples.</p>
                <button onClick={() => setPage("sensors")}>Inspect sensor diagnostics</button>
              </div>
            )}
            {mode === "live" && scan && module && !mappedRooms.some((r) => inRoom(module, r)) && (
              <div className="panel">
                <strong>Check radar placement</strong>
                <p>The saved radar position is outside the labelled rooms. Match its position and facing direction to the physical radar; the scan alone cannot calibrate it.</p>
                <button onClick={() => setPage("setup")}>Adjust radar placement</button>
              </div>
            )}
            <div className="metrics">
              <Metric
                label={`Motion now${module ? ` · ${module.name}` : ''}`}
                value={motionIndicator(!!live?.transport_online,live?.motionEvidence,!!live?.csi?.connected,!!live?.radar_verified).value}
                detail={motionIndicator(!!live?.transport_online,live?.motionEvidence,!!live?.csi?.connected,!!live?.radar_verified).detail}
              />
              <Metric
                label="Radar reflections"
                value={anyFresh ? String(currentTracks.length) : "—"}
                detail="Candidate groups, not people"
              />
              <Metric
                label="Home mode"
                value={cfg.away ? "Away" : "At home"}
                detail={
                  cfg.away ? "Motion review rule armed" : "Monitoring overview"
                }
              />
            </div>
            <div className="overview-grid">
              <section className="panel floor-panel">
                <div className="panel-heading">
                  <div>
                    <span className="tiny">
                      {scan ? "YOUR SCANNED SPACE" : "GROUND FLOOR"}
                    </span>
                    <h2>Your home at a glance</h2>
                  </div>
                  <button className="text-btn" onClick={() => setPage("setup")}>
                    Edit layout <ArrowUpRight size={16} />
                  </button>
                </div>
                <div className="button-row">
                  <label>
                    Scanned space
                    <select value={scan?.id || ""} onChange={(e) => {
                      const model = models.find((m) => m.id === e.target.value);
                      if (model) void activateScan(model);
                    }}>
                      <option value="" disabled>Choose an uploaded 3D space</option>
                      {models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
                    </select>
                  </label>
                  <button onClick={() => setPage("setup")}>Upload or manage 3D spaces</button>
                </div>
                {showingScanSnapshot && <p role="status" className="muted small">Showing the last non-empty PB0 radar preview from {module?.name}. These dots are historical and are not a current person position.</p>}
                {scan && !footprint ? (
                  <div className="scan-plan-status" role="status">
                    {scanState?.error
                      ? `Could not process this scan: ${scanState.error}`
                      : "Processing your scan’s layout…"}
                  </div>
                ) : (
                  <div
                    className="floor-map"
                    style={{ aspectRatio: `${maxX}/${maxZ}` }}
                  >
                    {scan && (
                      <Suspense
                        fallback={<p role="status">Loading spatial view…</p>}
                      >
                        <Scene
                          rooms={planRooms}
                          modules={planModules}
                          tracks={[]}
                          model={scan}
                          plan
                          planBounds={bounds}
                        />
                      </Suspense>
                    )}
                    <svg
                      viewBox={planViewBox(
                        maxX,
                        maxZ,
                        bounds.minX,
                        bounds.minZ,
                      )}
                      role="img"
                      aria-label="Interactive top-down home floor plan"
                    >
                      {planRooms.map((r) => (
                        <g
                          key={r.id}
                          role="button"
                          tabIndex={0}
                          aria-label={"Open " + r.name}
                          onMouseEnter={() => setHover(r.id)}
                          onMouseLeave={() => setHover(null)}
                          onFocus={() => setHover(r.id)}
                          onBlur={() => setHover(null)}
                          onPointerDown={(e) => {
                            if (e.pointerType !== "mouse")
                              roomGesture.current.begin(
                                e.clientX,
                                e.clientY,
                                () => setHover(r.id),
                              );
                          }}
                          onPointerMove={(e) => {
                            if (e.pointerType !== "mouse")
                              roomGesture.current.move(e.clientX, e.clientY);
                          }}
                          onPointerUp={() => roomGesture.current.end()}
                          onPointerCancel={() => roomGesture.current.cancel()}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setSelected(r.id);
                            }
                          }}
                          onClick={() => {
                            if (roomGesture.current.consumeClick()) return;
                            if (placing) {
                              setMessage(
                                "Choose a position inside the room using the placement map in Setup.",
                              );
                              return;
                            }
                            setSelected(r.id);
                          }}
                        >
                          {r.boundary?.length ? (
                            <path d={roomPath(r)} className="room scan-room" />
                          ) : (
                            <>
                              <rect
                                className={
                                  scan
                                    ? "room scan-space"
                                    : scan
                                      ? "room scan-room"
                                      : "room"
                                }
                                x={r.x + 0.04}
                                y={r.z + 0.04}
                                width={r.width - 0.08}
                                height={r.depth - 0.08}
                                rx=".04"
                              />
                            </>
                          )}
                          <text
                            x={r.x + 0.3}
                            y={r.z + 0.5}
                            className="room-name"
                          >
                            {r.name}
                          </text>
                          <text
                            x={r.x + 0.3}
                            y={r.z + 0.86}
                            className="room-status"
                          >
                            {planModules.some((m) =>
                              r.id === scanArea?.id
                                ? inRoom(m, r)
                                : scan ? inRoom(m, r) : m.roomId === r.id,
                            )
                              ? roomHasEvidence(r)
                                ? `${roomTracks(r).length} candidate groups`
                                : "Waiting for sensor"
                              : "No sensor assigned"}
                          </text>
                        </g>
                      ))}
                      <RouterOverlay router={visibleRouter(cfg,scan,footprint)} modules={planModules}/>
                      {planModules.map((m) => (
                        <g key={m.id} aria-label={"Sensor " + m.name}>
                          <RadarDirection module={m} />
                          <circle
                            cx={m.x}
                            cy={m.z}
                            r=".13"
                            className="sensor-icon"
                          />
                          <path
                            d={`M${m.x - 0.16},${m.z + 0.2} Q${m.x},${m.z + 0.4} ${m.x + 0.16},${m.z + 0.2}`}
                            className="sensor-wave"
                          />
                        </g>
                      ))}
                      {mapRadarPoints
                        .filter(({point}) => point.x >= bounds.minX && point.x <= bounds.minX + maxX && point.z >= bounds.minZ && point.z <= bounds.minZ + maxZ)
                        .map(({point, ageSeconds}, i) => (
                          <circle
                            key={i}
                            cx={point.x}
                            cy={point.z}
                            r=".085"
                            opacity={mode === "live" && !showingScanSnapshot ? Math.max(0.22, 1 - ageSeconds / RADAR_MAP_ECHO_SECONDS) : 1}
                            className="reflection-dot"
                          />
                        ))}
                      {tracks
                        .filter((t) => t.x >= bounds.minX && t.x <= bounds.minX + maxX && t.z >= bounds.minZ && t.z <= bounds.minZ + maxZ)
                        .map((t) => (
                          <g key={t.key || t.id}
                            opacity={mode === "recorded" ? 1 : Math.max(0.24, Math.min(1,
                              (TRACK_DISPLAY_SECONDS - Math.max(0, (liveAggregate?.now || Date.now() / 1000) - t.seen)) /
                              (TRACK_DISPLAY_SECONDS - TRACK_CURRENT_SECONDS))) }
                            aria-label={mode === "live" && !isCurrentTrack(t, liveAggregate?.now || Date.now() / 1000) ? "Recent radar reflection" : "Current radar reflection"}>
                            <polyline
                              className="trail"
                              points={t.trail
                                .map((p) => `${p.x},${p.z}`)
                                .join(" ")}
                            />
                            <circle
                              cx={t.x}
                              cy={t.z}
                              r=".1"
                              className="track-dot"
                            />
                            <circle
                              cx={t.x}
                              cy={t.z}
                              r=".19"
                              className="track-ring"
                            />
                          </g>
                        ))}
                    </svg>
                    {hoverRoom && (
                      <div className="room-tooltip">
                        <strong>{hoverRoom.name}</strong>
                        <span>People: unavailable</span>
                        <span>
                          {roomTracks(hoverRoom).length} candidate reflection
                          groups
                        </span>
                        <span>
                          Activity:{" "}
                          {roomTracks(hoverRoom).some(
                            (t) => Math.abs(t.velocity) >= 0.5,
                          )
                            ? "Moving reflections"
                            : "Unclassified"}
                        </span>
                        <small>Click to explore in 3D</small>
                      </div>
                    )}
                  </div>
                )}
                <div className="map-legend">
                  <span>
                    <i className="legend-sensor" />
                    Radar position
                  </span>
                  <span>
                    <i className="legend-dot" />
                    Radar reflection · recent markers fade after {RADAR_MAP_ECHO_SECONDS} s
                  </span>
                  <span>
                    {scan
                      ? footprint
                        ? `${scan.name} · ${footprint.width.toFixed(2)} × ${footprint.depth.toFixed(2)} m`
                        : "Processing imported scan"
                      : "Example layout · customize in Setup"}
                  </span>
                </div>
                {mode === "live" && !showingScanSnapshot && live?.monitoring && (
                  <p role="status" className="muted small">
                    {mapRadarPoints.length
                      ? `${mapRadarPoints.length} recent radar ${mapRadarPoints.length === 1 ? "reflection" : "reflections"} on the map; these are not confirmed people.`
                      : `No radar coordinates in the last ${RADAR_MAP_ECHO_SECONDS} seconds from ${module?.name || "the active sensor"}. A connected ESP does not guarantee a detected target.`}
                  </p>
                )}
                {scan && footprint && !mappedRooms.length && (
                  <p className="muted small">
                    This is your scan’s footprint. Name and mark rooms in Setup
                    to show individual room details.
                  </p>
                )}
                {mode === "recorded" && (
                  <div className="playback">
                    <button
                      aria-label={playing ? "Pause replay" : "Play replay"}
                      onClick={() => setPlaying((p) => !p)}
                    >
                      {playing ? <Pause size={16} /> : <Play size={16} />}
                    </button>
                    <input
                      type="range"
                      aria-label="Recorded report"
                      min="0"
                      max={(capture?.frames.length || 1) - 1}
                      value={index}
                      onChange={(e) => {
                        setIndex(Number(e.target.value));
                        setPlaying(false);
                      }}
                    />
                    <small>
                      Report {index + 1} / {capture?.frames.length}
                    </small>
                  </div>
                )}
              </section>
              <div className="overview-side">
                <section className="mode-card">
                  <div className="mode-icon">
                    <Shield size={23} />
                  </div>
                  <h2>
                    {cfg.away ? "Keeping an eye out." : "Home feels like home."}
                  </h2>
                  <p>
                    {cfg.away
                      ? "Persistent moving reflections raise a review event."
                      : "Arm Away mode to flag movement while you are out."}
                  </p>
                  <button
                    className={cfg.away ? "secondary" : "primary"}
                    onClick={() => {
                      if (!cfg.away && mode === "live") {
                        if ("Notification" in window && Notification.permission === "default")
                          void Notification.requestPermission();
                        if (live?.radar_verified && !live.monitoring)
                          void action("/api/monitoring", { moduleId: module?.id, enabled: true });
                      }
                      if (cfg.away) setMotionAlert(null);
                      setCfg((c) => ({
                        ...c,
                        away: !c.away,
                        dataSource: mode,
                      }));
                      latched.current = false;
                      awayCount.current = 0;
                    }}
                  >
                    {cfg.away ? "Return to At home" : "Enable Away mode"}{" "}
                    <ArrowUpRight size={16} />
                  </button>
                  <small>
                    {mode === "recorded"
                      ? "Events are clearly marked as replay."
                      : "Local alerts; remote delivery is not connected."}
                  </small>
                </section>
              </div>
            </div>
            <section className="room-list">
              {planRooms.map((r) => (
                <button
                  key={r.id}
                  className="room-card"
                  onClick={() => setSelected(r.id)}
                >
                  <div>
                    <Layers size={19} />
                  </div>
                  <h3>{r.name}</h3>
                  <p>
                    {
                      planModules.filter((m) =>
                        scan ? inRoom(m, r) : m.roomId === r.id,
                      ).length
                    }{" "}
                    sensor assigned
                  </p>
                  <span>
                    {roomHasEvidence(r)
                      ? `${roomTracks(r).length} candidate groups`
                      : "No fresh room evidence"}
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              ))}
            </section>
          </>
        )}
        {page === "home" && room && (
          <>
            <button className="text-btn back" onClick={() => setSelected(null)}>
              <ChevronLeft size={16} />
              Back to overview
            </button>
            <div className="room-detail">
              <section className="panel">
                <div className="panel-heading">
                  <h2>Spatial view</h2>
                  <span className="tag">
                    {spatialContext?.role === "room"
                      ? "Imported room scan"
                      : spatialContext?.role === "home"
                        ? "Imported home scan"
                        : "Schematic room geometry"}
                  </span>
                </div>
                <div className="spatial">
                  <Suspense
                    fallback={<p role="status">Loading spatial view…</p>}
                  >
                    <Scene
                      rooms={spatialContext!.rooms}
                      modules={spatialContext!.modules}
                      tracks={tracks}
                      points={points}
                      model={spatialContext!.model}
                      modelOrigin={spatialContext!.modelOrigin}
                      selected={room}
                      planBounds={bounds}
                    />
                  </Suspense>
                </div>
                {spatialContext?.missingRoomModel && (
                  <p className="muted small">
                    The assigned room scan is unavailable.{" "}
                    {spatialContext.model
                      ? "The home scan is shown."
                      : "Schematic room geometry is shown."}
                  </p>
                )}
                <p className="muted small">
                  Drag to orbit · pinch or scroll to zoom. Small dots are radar
                  reflections; larger dots are candidate groups.
                </p>
              </section>
              <section className="panel room-insights">
                <span className="tiny">ROOM DETAILS</span>
                <h2>{room.name}</h2>
                <Metric
                  label="Candidate groups"
                  value={
                    roomHasEvidence(room)
                      ? String(roomTracks(room).length)
                      : "—"
                  }
                  detail="Partial coordinates can miss or merge groups"
                />
                <Metric
                  label="Activity"
                  value={
                    roomTracks(room).some((t) => Math.abs(t.velocity) >= 0.5)
                      ? "Moving reflections"
                      : "Unclassified"
                  }
                  detail="Velocity rule, not activity recognition"
                />
              </section>
            </div>
          </>
        )}
        {page === "sensors" && (
          <>
            <div className="section-title">
              <h2>Your sensing modules</h2>
              <button className="primary" onClick={() => setDialog("module")}>
                <Plus size={16} />
                Add module
              </button>
            </div>
            {cfg.modules.map((m, i) => (
              <section className="panel sensor-card" key={m.id}>
                <Radio />
                <div>
                  <h3>{m.name}</h3>
                  <p>
                    {cfg.rooms.find((r) => r.id === m.roomId)?.name} · x{" "}
                    {m.x.toFixed(1)} m, y {m.z.toFixed(1)} m · yaw {m.yaw}°
                  </p>
                  <small>
                    {m.id === module?.id
                      ? "Active input binding"
                      : "Independent module connection"}
                  </small>
                </div>
                <span className="tag">
                  {liveAggregate?.nodes?.[m.id]?.radar_verified
                    ? "Verified"
                    : "Not verified"}
                </span>
              </section>
            ))}
            <section className="panel">
              <h2>Connect the ESP</h2>
              <label>
                Active sensor input
                <select
                  aria-label="Active sensor input"
                  value={module?.id || ""}
                  onChange={(e) => {
                    const m = cfg.modules.find((m) => m.id === e.target.value);
                    setCfg((c) => ({
                      ...c,
                      activeModuleId: m?.id,
                      away: false,
                    }));
                    if (m) setPort(m.port);
                  }}
                >
                  {cfg.modules.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </label>
              <p>
                For USB connections, close Arduino’s Serial Monitor first. For
                wireless sensing, use Wi-Fi pairing below after installing the
                configured Wi-Fi firmware on the ESP.
              </p>
              <label>
                Available serial port
                <select value={port} onChange={(e) => setPort(e.target.value)}>
                  {!live?.ports?.length && <option value="">No USB serial ports detected</option>}
                  {live?.ports?.map((p) => <option key={p.port} value={p.port}>{p.name} · {p.port}</option>)}
                </select>
              </label>
              <div className="button-row">
                <button
                  className="primary"
                  onClick={() => {
                    setCfg((c) => ({
                      ...c,
                      modules: c.modules.map((m) =>
                        m.id === module?.id ? { ...m, port } : m,
                      ),
                    }));
                    api("/api/home", {
                      ...cfg,
                      activeModuleId: module?.id,
                      modules: cfg.modules.map((m) =>
                        m.id === module?.id ? { ...m, port } : m,
                      ),
                    })
                      .then(() =>
                        action("/api/connect", { port, moduleId: module?.id }),
                      )
                      .catch((e) => setError(e.message));
                  }}
                  disabled={!port || !!live?.transport_online || !!live?.connected}
                >
                  Connect ESP
                </button>
                <button
                  onClick={() =>
                    action("/api/disconnect", { moduleId: module?.id })
                  }
                >
                  Disconnect
                </button>
                <button
                  onClick={() => action("/api/scan", { moduleId: module?.id })}
                  disabled={
                    !live?.radar_verified ||
                    live.scan_pending ||
                    live.scan_running
                  }
                >
                  Start 20-second scan
                </button>
                <button
                  disabled={!live?.radar_verified}
                  onClick={() =>
                    action("/api/monitoring", {
                      moduleId: module?.id,
                      enabled: !live?.monitoring,
                    })
                  }
                >
                  {live?.monitoring
                    ? "Stop monitoring"
                    : "Start persistent monitoring"}
                </button>
                <button
                  onClick={() => action("/api/stop", { moduleId: module?.id })}
                  disabled={!live?.scan_running}
                >
                  Stop
                </button>
                <button
                  onClick={async () => {
                    try {
                      exportFile(
                        JSON.stringify(
                          await api(
                            "/api/export?moduleId=" +
                              encodeURIComponent(module?.id || ""),
                          ),
                          null,
                          2,
                        ),
                        "haven-live-capture.json",
                      );
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  <Download size={16} />
                  Export live capture
                </button>
              </div>
              <p role="status">{live?.message || "Service unavailable"}</p>
              {live?.transport_online && !live?.radar_verified && <p className="muted small">ESP transport is receiving packets, but the radar has not returned a valid version. Check RD-60 power, common ground, PB0/PB1 wiring, UART DIP isolation and control UART baud before expecting map detections.</p>}
              {live?.connected && (
                <p className="muted small">
                  Connection: {live.transport === "wifi" ? "Home Wi-Fi" : "USB"}
                </p>
              )}
              <p className="muted small">
                {live?.monitoring
                  ? "Monitoring is active in the local service. Finite scans repeat, with gaps during reconfiguration."
                  : ""}{" "}
                {live?.scan_cycles
                  ? `${live.scan_cycles} scan cycles started.`
                  : ""}
              </p>
              <details>
                <summary>Diagnostic log</summary>
                <pre>{live?.logs.join("\n")}</pre>
              </details>
              <h3>mmWave UART1 byte stream</h3>
              <p>{live?.radar_uart?.bytes || 0} bytes received over Wi-Fi · {live?.radar_uart?.retained_bytes || 0} bytes retained · {live?.radar_uart?.dropped_bytes || 0} device-reported dropped bytes.</p>
              <p className="muted small">RD-60 command-UART coordinates appear in live captures after a verified scan. UART1 chunks are separate, bounded and unparsed—not a validated complete point cloud. A silent PA8 produces no bytes to forward.</p>
              <button disabled={!live?.radar_uart?.bytes} onClick={async () => {
                try {exportFile(JSON.stringify(await api("/api/radar/raw"),null,2),"haven-rd60-uart1-raw.json");}
                catch(error) {setError((error as Error).message);}
              }}>Export raw mmWave UART1</button>
            </section>
            <EspSetup />
            <section className="panel" id="radar-wifi-connection" tabIndex={-1} aria-labelledby="radar-wifi-heading">
              <h2 id="radar-wifi-heading">Connect over home Wi-Fi</h2>
              <WifiDevices onAdd={() => setDialog("module")} request={api} sensors={cfg.modules.map(m=>({id:m.id,name:m.name}))} selectedId={module?.id} selectedConnected={!!(module && (liveAggregate?.nodes?.[module.id]?.transport_online || liveAggregate?.nodes?.[module.id]?.connected))} onSelect={id => setCfg(c => ({...c,activeModuleId:id}))} save={async id=>{await api("/api/home",{...cfg,activeModuleId:id});}} />

              <p>
                {live?.connected && live.transport === "wifi"
                  ? `Connected over Wi-Fi. ${live.radar_verified ? "Radar verified." : "Verifying radar…"} ${live.csi?.connected ? "CSI readings are arriving." : "Waiting for fresh CSI readings."}`
                  : live?.csi?.connected
                    ? "Connected over Wi-Fi in CSI-only mode. Fresh CSI readings are arriving; radar sensing remains unavailable."
                  : "Power the ESP with its configured Wi-Fi firmware and keep Haven running on the same reachable network. An existing paired ESP connects automatically; use Allow reconnection in the device list if you previously chose Disconnect."}
                {" "}To add another ESP, find an available device above and add it to the selected sensor.
              </p>
              <p className="muted small">
                New-device pairing requires workspace sign-in. Secure pairing keys
                are created automatically when you connect an available ESP. Keep Haven running
                and the radar and ESP powered after removing the computer’s USB
                cable.
              </p>
              {authStatus && !authStatus.enrolled && !live?.connected && (
                <button onClick={() => setAuthEnrolling(true)}>
                  Set up sign-in for Wi-Fi pairing
                </button>
              )}
              <p className="muted small">
                For a demo, connect the ESP and laptop to your own 2.4 GHz
                hotspot or router. This firmware does not log into a venue’s
                captive portal. The ESP needs a reachable HTTPS address for
                Haven; the laptop’s localhost address cannot be used by the ESP.
              </p>
              <p>
                Selected sensor: {module?.name || "Choose a sensor"} · ID:{" "}
                {module?.id || "—"}
              </p>
              <SensorNameEditor module={module} onRename={async (name) => {
                if (!module) throw Error("Choose a sensor first.");
                const next = renameSensor(cfg,module.id,name);
                await api("/api/home",next);setCfg(next);setMessage("Sensor name saved. Pairing is unchanged.");
              }}/>
              <details>
                <summary>Advanced connection recovery</summary>
                <p className="muted small">Not needed for normal setup. Manual key creation replaces the existing key and requires updating the ESP. Revoking a key blocks that ESP’s access until it is paired again. These keys are device credentials, not your Wi-Fi password.</p>
              <div className="button-row">
                <button
                  disabled={
                    !module ||
                    !authStatus?.enrolled ||
                    live?.connected ||
                    wifiPairing
                  }
                  onClick={async () => {
                    setWifiPairing(true);
                    setWifiKey(null);
                    setError("");
                    try {
                      await api("/api/home", cfg);
                      const paired = await api("/api/wifi/pair", {
                        moduleId: module?.id,
                      });
                      setWifiKey({
                        moduleId: paired.moduleId,
                        token: paired.deviceToken,
                      });
                      setMessage(
                        "Pairing key created. Copy it into this ESP’s private firmware settings. Any previous key is replaced.",
                      );
                    } catch (error) {
                      setError((error as Error).message);
                    } finally {
                      setWifiPairing(false);
                    }
                  }}
                >
                  Create Wi-Fi pairing key
                </button>
                <button
                  disabled={
                    !module ||
                    live?.connected ||
                    wifiPairing
                  }
                  onClick={() =>
                    action("/api/wifi/reset", { moduleId: module?.id })
                  }
                >
                  Reset Wi-Fi connection
                </button>
                <button
                  disabled={
                    !module ||
                    !authStatus?.enrolled ||
                    live?.connected ||
                    wifiPairing
                  }
                  onClick={async () => {
                    setWifiKey(null);
                    await action("/api/wifi/revoke", { moduleId: module?.id });
                  }}
                >
                  Revoke Wi-Fi key
                </button>
              </div>
              {wifiKey?.moduleId === module?.id && wifiKey && (
                <div>
                  <label>
                    Private pairing key (shown once)
                    <input
                      type="password"
                      readOnly
                      value={wifiKey.token}
                      autoComplete="off"
                    />
                  </label>
                  <div className="button-row">
                    <button
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(wifiKey.token);
                          setMessage("Pairing key copied.");
                        } catch {
                          setError(
                            "Copy is unavailable. Select and copy the key from the field.",
                          );
                        }
                      }}
                    >
                      Copy pairing key
                    </button>
                    <button onClick={() => setWifiKey(null)}>Hide key</button>
                  </div>
                  <p className="muted small">
                    Stored only in this page while visible. Keep the key
                    private; it authorizes this sensor’s readings and commands.
                  </p>
                </div>
              )}
              </details>
              <p className="muted small">
                Brief connection faults stop the scan and restart the ESP connection automatically.
                Wait for radar verification, then calibrate the quiet area again.
                After choosing Disconnect, use Allow reconnection in the device list to allow wireless delivery again.
              </p>
            </section>
            <section className="panel">
              <h2>Prepare an activity session</h2>
              <p>
                After one controlled finite scan, annotate what you observed and
                save it for review and evaluation. These labels are your notes,
                not model predictions. Mixed activities need separate reviewed
                sessions.
              </p>
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  const form = new FormData(e.currentTarget);
                  const save =
                    (
                      (e.nativeEvent as SubmitEvent)
                        .submitter as HTMLButtonElement | null
                    )?.value !== "export";
                  setSessionSaving(true);
                  setError("");
                  try {
                    const value = await api(
                      save ? "/api/dataset/save" : "/api/dataset/export",
                      {
                        moduleId: module?.id,
                        roomId: String(form.get("roomId") || ""),
                        sessionId: String(form.get("sessionId") || "").trim(),
                        participantId: String(
                          form.get("participantId") || "",
                        ).trim(),
                        label: form.get("label"),
                      },
                    );
                    if (save) setSessionRevision((v) => v + 1);
                    else
                      exportFile(
                        JSON.stringify(value, null, 2),
                        "haven-annotated-session.json",
                      );
                    setMessage(
                      save
                        ? "Recording saved to Haven. Review it in Saved activity recordings below."
                        : "Operator-annotated preview exported. Review labels and keep participant/session splits separate before training.",
                    );
                  } catch (error) {
                    setError((error as Error).message);
                  } finally {
                    setSessionSaving(false);
                  }
                }}
              >
                <label>
                  Room observed during this session
                  <select name="roomId" required defaultValue={cfg.rooms.some((room) => room.id === module?.roomId) ? module?.roomId : ""} key={module?.id}>
                    <option value="" disabled>Choose a room</option>
                    {cfg.rooms.map((room) => <option key={room.id} value={room.id}>{room.name}{module?.roomId === room.id ? " · sensor placed here" : " · location not sensor-verified"}</option>)}
                  </select>
                </label>
                <p className="muted small">Record one room and one activity per session. If the sensor is not placed in that room, the location is your observation only and the recording is excluded from training export.</p>
                <label>
                  Session identifier
                  <input
                    name="sessionId"
                    required
                    maxLength={100}
                    placeholder="living-room-session-001"
                  />
                </label>
                <label>
                  Participant pseudonym
                  <input
                    name="participantId"
                    required
                    maxLength={100}
                    placeholder="participant-A or empty-room"
                  />
                </label>
                <label>
                  Observed activity
                  <select name="label" defaultValue="unlabelled">
                    <option value="unlabelled">Unlabelled / uncertain</option>
                    <option value="empty-room">Empty room</option>
                    <option value="walking">Walking</option>
                    <option value="standing">Standing</option>
                    <option value="sitting">Sitting</option>
                    <option value="lying-down">Lying down</option>
                  </select>
                </label>
                <button
                  className="primary"
                  type="submit"
                  value="save"
                  disabled={
                    sessionSaving ||
                    mode !== "live" ||
                    !live?.radar_verified ||
                    live.scan_pending ||
                    live.scan_running ||
                    live.monitoring ||
                    !live?.frames?.length
                  }
                >
                  <Download size={16} />
                  Save to Haven
                </button>
                <button
                  type="submit"
                  value="export"
                  disabled={
                    sessionSaving ||
                    mode !== "live" ||
                    !live?.radar_verified ||
                    live.scan_pending ||
                    live.scan_running ||
                    live.monitoring ||
                    !live?.frames?.length
                  }
                >
                  Export annotated session
                </button>
              </form>
              <p className="muted small">
                Finish the scan and stop persistent monitoring first. The export
                retains partial coordinates, module placement and host receipt
                times and overlapping CSI when available. Save before starting another scan or restarting Haven. Labels describe what you observed.
              </p>
            </section>
            <SessionLibrary
              revision={sessionRevision}
              request={api}
              download={exportFile}
            />
            <section className="panel">
              <Wifi />
              <h2>Wi-Fi CSI</h2>
              <p>
                {live?.csi?.connected
                  ? `CSI receiving: ${live.csi.samples} samples · ${live.csi.approx_rate?.toFixed(1)} samples/s · channel ${live.csi.channel} · RSSI ${live.csi.rssi} dBm · ${live.csi.dropped || 0} dropped.`
                  : "No fresh CSI stream is connected."}
              </p>
              <p>{live?.activityEstimate?.enabled
                ? `Experimental activity estimate: ${live.activityEstimate.label?.replace(/-/g, " ")} · ${((live.activityEstimate.model_vote || 0) * 100).toFixed(0)}% model vote · ${live.activityEstimate.branch}. This is a sensor-window estimate, not an identified person or medical reading.`
                : "No live activity estimate is available. A reviewed target model and continuous paired readings are required."}</p>
              <p>Keep the router and sensor fixed. Leave the sensing area still for 30 seconds to calibrate motion changes.</p>
              <button disabled={!live?.csi?.connected || live.csi.motion?.status === "calibrating"} onClick={async () => {
                try { await api("/api/csi/calibrate", {}); }
                catch (error) { alert(error instanceof Error ? error.message : "Calibration could not start"); }
              }}>Calibrate quiet area</button>
              <button disabled={!live?.csi?.samples} onClick={async () => {
                try { exportFile(JSON.stringify(await api("/api/csi/export"), null, 2), "haven-csi-readings.json"); }
                catch (error) { setError(error instanceof Error ? error.message : "CSI export could not complete"); }
              }}>Export CSI readings</button>
              <p>{live?.csi?.motion?.status === "calibrating"
                ? `Keep still: ${live.csi.motion.remaining_seconds} seconds remaining.`
                : live?.csi?.motion?.status === "motion" ? "CSI: motion change detected."
                : live?.csi?.motion?.status === "quiet" ? "CSI: channel is quiet."
                : live?.csi?.motion?.status === "calibration_failed" ? "Not enough continuous samples. Try calibration again."
                : "CSI motion needs a quiet calibration."} This detects channel changes; it does not identify an activity or count people.</p>
              <p>{live?.motionEvidence?.status === "corroborated_motion" ? "Both CSI and radar show motion."
                : live?.motionEvidence?.status === "sources_disagree" ? "CSI and radar show different motion evidence."
                : live?.motionEvidence?.status === "no_motion_evidence" ? "Neither source currently shows motion evidence."
                : "Both calibrated CSI and fresh radar readings are needed to compare motion."}</p>
            </section>
          </>
        )}
        {page === "events" && (
          <section className="panel">
            <div className="panel-heading">
              <h2>Events to review</h2>
              <button disabled={!cfg.events.length} onClick={async () => {
                if (!window.confirm("Delete all saved events? Existing downloaded exports remain unchanged.")) return;
                try { await api("/api/events/clear", {}); setCfg(c => ({...c, events: []})); }
                catch (error) {setError((error as Error).message);}
              }}>Delete all events</button>
            </div>
            <p className="muted small">Movement is grouped per sensor. Each event stays open until four minutes without detected motion, or Away mode is disabled. Quiet or lost data does not establish that a person left.</p>
            {cfg.events.length ? (
              cfg.events.map((e) => (
                <div className="event" key={e.id}>
                  <div className="event-icon">
                    <Shield size={18} />
                  </div>
                  <div>
                    <strong>{e.kind}</strong>
                    <p>
                      {e.room} · Started: {new Date(e.at).toLocaleString(undefined, {year:"numeric", month:"short", day:"numeric", hour:"numeric", minute:"2-digit", second:"2-digit", hour12:true})}
                      <br />Stopped: {e.endedAt ? new Date(e.endedAt).toLocaleString(undefined, {year:"numeric", month:"short", day:"numeric", hour:"numeric", minute:"2-digit", second:"2-digit", hour12:true}) : e.status === "open" ? "Open — waiting for four-minute quiet timeout" : "Not recorded (legacy event)"}
                      {e.lastMotionAt && <><br />Last detected motion: {new Date(e.lastMotionAt).toLocaleString(undefined, {year:"numeric", month:"short", day:"numeric", hour:"numeric", minute:"2-digit", second:"2-digit", hour12:true})}</>}
                      {e.stopReason && <><br />{e.stopReason}</>}
                    </p>
                    <span className="tag">
                      {e.source === "recorded"
                        ? "Recorded replay"
                        : "Live preview"}
                    </span>
                  </div>
                  <div>
                    <button onClick={() => exportFile(JSON.stringify({schema:"haven-motion-episode-v1", event:e, note:"Partial console previews, not identified people or complete radar/CSI acquisition"}, null, 2), `haven-event-${e.id}.json`)}><Download size={16}/>Export event</button>
                    <EventPlayback event={e} models={models} />
                  </div>
                  <button
                    disabled={e.acknowledged}
                    onClick={() =>
                      setCfg((c) => ({
                        ...c,
                        events: c.events.map((v) =>
                          v.id === e.id ? { ...v, acknowledged: true } : v,
                        ),
                      }))
                    }
                  >
                    {e.acknowledged ? (
                      <>
                        <Check size={16} />
                        Reviewed
                      </>
                    ) : (
                      "Mark reviewed"
                    )}
                  </button>
                </div>
              ))
            ) : (
              <div className="empty">
                <Shield />
                <h3>Nothing to review yet.</h3>
                <p>
                  Enable Away mode with a connected, verified radar to record detected movement.
                </p>
              </div>
            )}
            <p className="muted small">
              These are motion review events, not confirmed intrusions. No detected movement does not establish that the space is empty.
            </p>
          </section>
        )}
        {page === "setup" && (
          <>
            <EmailSetup />
            <section className="panel">
              <h2>Background notifications</h2>
              <div role="status">
                <p>
                  {!pushStatus
                    ? "Delivery status unavailable"
                    : !pushStatus.configured
                      ? "Server delivery is not configured"
                      : !pushStatus.enrolled
                        ? "Workspace sign-in setup is required"
                        : "Server delivery is configured; device receipt remains unverified"}
                </p>
                {pushStatus && (
                  <p className="muted small">
                    Registered devices in this workspace: {pushStatus.devices} ·
                    Pending: {pushStatus.states.pending || 0} · Accepted by push
                    service: {pushStatus.states.accepted_by_push_service || 0} ·
                    Failed: {pushStatus.states.failed || 0} · Expired:{" "}
                    {pushStatus.states.expired || 0} · Cancelled:{" "}
                    {pushStatus.states.cancelled || 0}
                  </p>
                )}
              </div>

              <p>
                Register this browser for Away review alerts. Server delivery
                configuration, sign-in and a supported secure connection are
                required. No delivery has been verified yet.
              </p>
              <div className="button-row">
                <button
                  onClick={async () => {
                    try {
                      setMessage(await enableBackgroundPush());
                    } catch (error) {
                      setError((error as Error).message);
                    }
                  }}
                >
                  Enable background notifications
                </button>
                <button
                  onClick={async () => {
                    try {
                      setMessage(await disableBackgroundPush());
                    } catch (error) {
                      setError((error as Error).message);
                    }
                  }}
                >
                  Disable for this browser
                </button>
              </div>
            </section>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="tiny">01 · YOUR SPACE</span>
                  <h2>Bring in your scan.</h2>
                </div>
                <label className="primary upload" style={{ cursor: "pointer" }} title="Upload a 3D scan (.glb, .obj, .gltf) or Polycam export">
                  <Upload size={16} />
                  Upload 3D scan
                  <input
                    type="file"
                    multiple
                    accept=".glb,.gltf,.obj,.bin,.png,.jpg,.jpeg,.webp"
                    onChange={(e) => importScan(e.target.files)}
                  />
                </label>
              </div>
              <p>
                Use a GLB, OBJ, or GLTF with its companion geometry and
                textures. A top-down view is rendered from the mesh. Room
                boundaries and sensor calibration are set below.
              </p>
              {models.length > 0 && (
                <div className="button-row">
                  <label>
                    Active scan
                    <select
                      value={scan?.id}
                      onChange={(e) => {
                        const model = models.find((m) => m.id === e.target.value);
                        if (model) void activateScan(model);
                      }}
                    >
                      {models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Scan vertical axis
                    <select
                      value={scan?.upAxis || "Y"}
                      onChange={(e) =>
                        updateScan({ upAxis: e.target.value as "Y" | "Z" })
                      }
                    >
                      <option value="Y">Y is up</option>
                      <option value="Z">Z is up</option>
                    </select>
                  </label>
                  <label>
                    Scan floor rotation (degrees)
                    <input
                      type="number"
                      min={-360}
                      max={360}
                      step={1}
                      value={scan?.yaw || 0}
                      onChange={(e) => {
                        const yaw = Number(e.target.value);
                        if (Number.isFinite(yaw) && Math.abs(yaw) <= 360)
                          updateScan({ yaw });
                      }}
                    />
                  </label>
                  <label>
                    Metres per model unit
                    <input
                      type="number"
                      min=".001"
                      max="100"
                      step=".001"
                      value={scan?.scale || 1}
                      onChange={async (e) => {
                        if (!scan) return;
                        const scale = Number(e.target.value);
                        if (scale <= 0 || !Number.isFinite(scale)) return;
                        const next = { ...scan, scale };
                        try {
                          await saveModel(next);
                          setModels(await listModels());
                          setScan(next);
                        } catch (error) {
                          setError((error as Error).message);
                        }
                      }}
                    />
                  </label>
                </div>
              )}
              <p className="muted small">
                {scan
                  ? "Your imported scan supplies the map dimensions. Name rooms and place sensors on its top view below."
                  : "Import your scan to replace the example layout with your space."}
              </p>
              {models.length > 0 && (
                <div aria-label="Uploaded 3D spaces">
                  {models.map((model) => (
                    <div className="button-row" key={model.id}>
                      <span>{model.name}</span>
                      <button disabled={cfg.homeModelId === model.id} onClick={() => void activateScan(model)}>
                        {cfg.homeModelId === model.id ? "Current scanned space" : "Use as scanned space"}
                      </button>
                      <button
                        aria-label={`Delete scan ${model.name}`}
                        disabled={cfg.homeModelId === model.id}
                        title={cfg.homeModelId === model.id ? "Switch to another scan before deleting this one" : "Remove this scan from the workspace"}
                        onClick={() => {setScanDeleteId(model.id); setScanDeleteError("");}}
                      >Delete</button>
                      {scanDeleteId === model.id && <div role="group" aria-label={`Confirm deletion of ${model.name}`}>
                        <p>Remove “{model.name}”, its companion files and its old room/router placements from this workspace? Sensors on this scan will be unplaced, not deleted. Saved recordings and original source files are unchanged.</p>
                        <button disabled={scanDeleteBusy} onClick={async () => {
                          setScanDeleteBusy(true); setScanDeleteError("");
                          try {
                            const result = await deleteSharedModel(model.id);
                            if (result.config) setCfg(result.config);
                            setModels(current => current.filter(item => item.id !== model.id));
                            setScanDeleteId(null);
                            setMessage(`${model.name} removed from the scan library.`);
                          } catch (error) {setScanDeleteError((error as Error).message);}
                          finally {setScanDeleteBusy(false);}
                        }}>{scanDeleteBusy ? "Deleting…" : "Confirm delete scan"}</button>
                        <button disabled={scanDeleteBusy} onClick={() => {setScanDeleteId(null); setScanDeleteError("");}}>Cancel</button>
                        {scanDeleteError && <p role="alert">{scanDeleteError}</p>}
                      </div>}
                    </div>
                  ))}
                </div>
              )}
              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  flexWrap: "wrap",
                  alignItems: "center",
                  marginTop: "12px",
                  marginBottom: "12px",
                }}
              >
                <label className="primary upload" style={{ cursor: "pointer" }}>
                  <Upload size={16} />
                  Upload 3D scan (.glb, .obj, .gltf)
                  <input
                    type="file"
                    multiple
                    accept=".glb,.gltf,.obj,.bin,.png,.jpg,.jpeg,.webp"
                    onChange={(e) => importScan(e.target.files)}
                  />
                </label>
                <button
                  type="button"
                  disabled={!capabilities?.polycam_api_configured}
                  onClick={async () => {
                    try {
                      const response = await api("/api/polycam/captures");
                      setPolyCaptures(response.captures || []);
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Browse Polycam captures
                </button>
                <a
                  href="https://poly.cam/docs/api"
                  target="_blank"
                  rel="noreferrer"
                  style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
                >
                  Polycam API documentation <ArrowUpRight size={14} />
                </a>
              </div>
              {polyCaptures.map((c) => (
                <div className="sensor-card" key={c.id}>
                  <span>{c.name}</span>
                  <button
                    onClick={async () => {
                      try {
                        const links = await api(
                          "/api/polycam/artifacts?id=" +
                            encodeURIComponent(c.id),
                        );
                        exportFile(
                          JSON.stringify(links, null, 2),
                          c.name + "-artifact-links.json",
                        );
                        setMessage(
                          "Artifact links exported. Download a model and import it locally. Links expire after one hour.",
                        );
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    Get export links
                  </button>
                </div>
              ))}
            </section>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="tiny">02 · ROOM BOUNDARIES</span>
                  <h2>Make every room a place.</h2>
                </div>
              </div>
              <p>
                Set boundary points on the scan, close each outline and name the
                room. Saved room details appear below once boundaries are
                defined.
              </p>

              {scan && footprint && (
                <RoomDrawing
                  key={`${scan.id}:${scan.scale}:${scan.upAxis}:${scan.yaw}`}
                  config={cfg}
                  model={scan}
                  footprint={footprint}
                  onApply={(next) => {
                    setCfg(next);
                    setError("");
                    setMessage(
                      "Named rooms saved from the house scan. Review sensor room assignments.",
                    );
                  }}
                />
              )}
              {cfg.rooms
                .filter(
                  (r) =>
                    r.boundary &&
                    r.boundary.length >= 3 &&
                    (!scan ||
                      r.planModelId === scan.id ||
                      r.modelId === scan.id),
                )
                .map((r) => (
                  <div className="defined-room" key={r.id}>
                    <label>
                      Room name
                      <input
                        aria-label={r.name + " name"}
                        value={r.name}
                        onChange={(e) =>
                          setCfg((c) => ({
                            ...c,
                            rooms: c.rooms.map((q) =>
                              q.id === r.id
                                ? { ...q, name: e.target.value }
                                : q,
                            ),
                          }))
                        }
                      />
                    </label>
                    <p className="muted small">
                      {r.boundary!.length} boundary points · Extent{" "}
                      {r.width.toFixed(2)} × {r.depth.toFixed(2)} m ·{" "}
                      {models.find((m) => m.id === r.modelId)?.name ||
                        "Home scan"}
                    </p>
                    <button onClick={() => {
                      setCfg((c) => ({ ...c, rooms: c.rooms.filter((q) => q.id !== r.id), modules: c.modules.map((m) => m.roomId === r.id ? { ...m, roomId: "" } : m) }));
                      setMessage("Boundary deleted.");
                    }}>Delete boundary</button>
                  </div>
                ))}
            </section>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="tiny">03 · SENSOR &amp; ROUTER PLACEMENT</span>
                  <h2>A small sensor. A precise position.</h2>
                </div>
                <button onClick={() => {setPage("sensors"); setWifiNavigationPending(true);}}>
                  <Plus size={16} />
                  Add module
                </button>
              </div>
              <p>
                {scan
                  ? "Choose Place router to mark your Wi-Fi router, or choose a sensor module. Tap the device’s actual location on the GLB top view."
                  : "Import your GLB above to place the sensor on your scanned space, or use the schematic below."}
                Set its orientation: 0° points down the floor plan, 90° points
                right. Confirm room boundaries and model scale above before
                placement.
              </p>
              <p className="muted small">
                Radar coverage: 120° sector, 8 m nominal range at the scan’s
                metre scale. Coverage beyond the displayed scan is cropped;
                walls and mounting affect actual detection.
              </p>
              <div className="router-placement-controls">
                <button type="button" aria-pressed={placingRouter} onClick={() => {setPlacingRouter(!placingRouter); setPlacing(null);}}>
                  <Wifi size={16}/>{storedRouter(cfg,scan) ? "Move router" : "Place router"}
                </button>
                <span className="muted small">{placingRouter ? "Tap the router’s actual position on the map." : "Choose a sensor or place your Wi-Fi router."}</span>
              </div>
              <select
                aria-label="Module to place"
                value={placing || ""}
                onChange={(e) => {setPlacing(e.target.value || null); setPlacingRouter(false);}}
              >
                <option value="">Choose a module to place</option>
                {cfg.modules.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
              <div aria-label="Radar map placements">
                {cfg.modules.map(sensor => {
                  const placed = planModules.some(m => m.id === sensor.id);
                  return <div className="button-row" key={sensor.id}>
                    <span>{sensor.name} · {placed ? "Placed on this map" : "Not placed on this map"}</span>
                    <button type="button" onClick={() => {setPlacing(sensor.id); setPlacingRouter(false); setMessage("Tap the radar’s actual position on the map.");}}>{placed ? "Move radar" : "Place radar"}</button>
                    <button type="button" disabled={!placed} aria-label={`Remove ${sensor.name} from map`} onClick={async () => {
                      if (!window.confirm(`Remove ${sensor.name} from the map? Its pairing, connection and saved recordings will remain. You can place it again later.`)) return;
                      try {
                        const next = removeModulePlacement(cfg, sensor.id);
                        await api("/api/home", next);
                        setCfg(next);
                        if (placing === sensor.id) setPlacing(null);
                        if (editingSensor === sensor.id) setEditingSensor(null);
                        setMessage(`${sensor.name} removed from the map. Device registration retained.`);
                      } catch (error) {setError((error as Error).message);}
                    }}>Remove from map</button>
                  </div>;
                })}
              </div>
              {scan && (
                <p className="muted small">
                  {footprint
                    ? `Scan extent: ${footprint.width.toFixed(2)} × ${footprint.depth.toFixed(2)} m at the current scale.`
                    : scanState?.error ||
                      "Processing the scan before placement…"}
                  {cfg.modules.length > planModules.length &&
                    " Some sensors need placement on this scan. Select one and tap its installed position; changing the scan, units or alignment requires placement review."}
                  {!mappedRooms.length &&
                    " Room names are unavailable in this file. Placement will save a Scanned space boundary from the GLB; you can name or divide it in Room boundaries."}
                </p>
              )}
              <div
                className="floor-map sensor-scan-map"
                style={{ aspectRatio: `${maxX}/${maxZ}` }}
              >
                {scan && (
                  <Suspense
                    fallback={
                      <p role="status">Processing scan for placement…</p>
                    }
                  >
                    <Scene
                      rooms={planRooms}
                      modules={planModules}
                      tracks={[]}
                      model={scan}
                      plan
                      planBounds={bounds}
                    />
                  </Suspense>
                )}
                <svg
                  className={"placement-map " + (placing || placingRouter ? "placing" : "")}
                  viewBox={planViewBox(maxX, maxZ, bounds.minX, bounds.minZ)}
                  role="img"
                  aria-label="Sensor and router placement map"
                  onClick={(e) => {
                    if (!placing && !placingRouter) return;
                    try {
                      const svg = e.currentTarget,
                        matrix = svg.getScreenCTM();
                      if (!matrix)
                        throw Error("The placement map is not ready yet.");
                      const p = svg.createSVGPoint();
                      p.x = e.clientX;
                      p.y = e.clientY;
                      const q = p.matrixTransform(matrix.inverse());
                      if (placingRouter) {
                        setCfg(placeRouter(cfg,{x:q.x,z:q.y},scan,footprint));
                        setPlacingRouter(false); setError(""); setMessage("Router position saved on this floor plan.");
                        return;
                      }
                      if (!placing) return;
                      const next = placeModule(
                        cfg,
                        placing,
                        { x: q.x, z: q.y },
                        scan,
                        footprint,
                      );
                      setCfg(next);
                      setError("");
                      const placed = next.modules.find(
                        (m) => m.id === placing,
                      )!;
                      setMessage(
                        "Sensor position saved in " +
                          next.rooms.find((r) => r.id === placed.roomId)!.name,
                      );
                    } catch (error) {
                      setError((error as Error).message);
                    }
                  }}
                >
                  {mappedRooms.map((r) => (
                    <g key={r.id}>
                      {r.boundary?.length ? (
                        <path d={roomPath(r)} className="room scan-room" />
                      ) : (
                        <>
                          <rect
                            x={r.x}
                            y={r.z}
                            width={r.width}
                            height={r.depth}
                            className={scan ? "room scan-room" : "room"}
                          />
                        </>
                      )}
                      <text x={r.x + 0.2} y={r.z + 0.5} className="room-name">
                        {r.name}
                      </text>
                    </g>
                  ))}
                  <RouterOverlay router={visibleRouter(cfg,scan,footprint)} modules={planModules}/>
                  <g pointerEvents={placingRouter ? "none" : undefined}>
                  {planModules.map((m) => (
                    <RadarDirection
                      key={"direction:" + m.id}
                      module={m}
                      onDirectionChange={(yaw) => {
                        setEditingSensor(m.id);
                        setCfg((c) => ({
                          ...c,
                          modules: c.modules.map((q) =>
                            q.id === m.id ? { ...q, yaw } : q,
                          ),
                        }));
                      }}
                    />
                  ))}
                  {planModules.map((m) => (
                    <circle
                      key={m.id}
                      cx={m.x}
                      cy={m.z}
                      r=".16"
                      className="sensor-icon sensor-action"
                      role="button"
                      tabIndex={0}
                      aria-label={`Edit ${m.name}`}
                      aria-expanded={editingSensor === m.id}
                      onMouseEnter={() => setEditingSensor(m.id)}
                      onFocus={() => setEditingSensor(m.id)}
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingSensor(m.id);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          e.stopPropagation();
                          setEditingSensor(m.id);
                        }
                      }}
                    >
                      <title>{`${m.name} · ${cfg.rooms.find((r) => r.id === m.roomId)?.name || "Unassigned"} · height ${m.height} m · yaw ${m.yaw}°. Click to edit or delete.`}</title>
                    </circle>
                  ))}
                  </g>
                </svg>
              </div>
              <p className="muted small">
                Hover, click or tap a sensor to see its details. Drag the dot at
                the end of its direction line to rotate its field of view.
              </p>
              <div className="router-details">
                <h3><Wifi size={17}/> Wi-Fi router position</h3>
                <p className="muted small">Amber diamond = router; green markers = sensors. Dashed lines show planned router-to-ESP links, not measured signal strength, radio coverage or a person’s location.</p>
                {storedRouter(cfg,scan) && !visibleRouter(cfg,scan,footprint) && <p role="status">Router placement needs review after a scan, scale, alignment or extent change. Choose Move router and tap its actual location again.</p>}
                {(() => {
                  const router = visibleRouter(cfg,scan,footprint);
                  if (!router) return <p>No reviewed router position on this floor plan.</p>;
                  return <>
                    <p>x {router.x.toFixed(2)} m · y {router.z.toFixed(2)} m · mounting height {router.height} m</p>
                    <div className="form-grid">
                      <label>Router name<input key={router.id + router.name} defaultValue={router.name} maxLength={80} onBlur={e => {try {setCfg(c => updateRouter(c,router.id,{name:e.target.value})); setError("");} catch(error) {setError((error as Error).message); e.target.value=router.name;}}}/></label>
                      <label>Router mounting height (m)<input type="number" min="0" max="20" step="0.1" value={router.height} onChange={e => {try {const next=updateRouter(cfg,router.id,{height:e.target.valueAsNumber}); setCfg(next);setError("");} catch(error) {setError((error as Error).message);}}}/></label>
                    </div>
                    <button onClick={() => {setCfg(c => ({...c,routers:(c.routers || []).filter(r => r.id !== router.id)})); setPlacingRouter(false);}}>Remove router position</button>
                  </>;
                })()}
              </div>
              <div className="sensor-selector">
                {cfg.modules.map((m) => (
                  <button
                    key={m.id}
                    aria-expanded={editingSensor === m.id}
                    onClick={() => setEditingSensor(m.id)}
                  >
                    {m.name}
                  </button>
                ))}
              </div>
              {cfg.modules
                .filter((m) => m.id === editingSensor)
                .map((m) => (
                  <div className="sensor-details" key={m.id}>
                    <h3>Sensor details</h3>
                    <label>
                      Device name
                      <input
                        value={m.name}
                        onChange={(e) =>
                          setCfg((c) => ({
                            ...c,
                            modules: c.modules.map((q) =>
                              q.id === m.id
                                ? { ...q, name: e.target.value }
                                : q,
                            ),
                          }))
                        }
                      />
                    </label>
                    <p className="muted small">
                      Device ID: {m.id} · Room:{" "}
                      {cfg.rooms.find((r) => r.id === m.roomId)?.name ||
                        "Unassigned"}
                      <br />
                      Position: {m.x.toFixed(2)}, {m.z.toFixed(2)} m · Port:{" "}
                      {m.port || "Not configured"}
                    </p>
                    <button
                      onClick={() => {
                        setPlacing(m.id);
                        setMessage(
                          "Tap the sensor’s new installed position on the map.",
                        );
                      }}
                    >
                      Move this sensor
                    </button>
                    <div className="module-edit">
                      <strong>{m.name}</strong>
                      <label>
                        Facing direction (°)
                        <input
                          type="number"
                          value={m.yaw}
                          min="-360"
                          max="360"
                          onChange={(e) =>
                            setCfg((c) => ({
                              ...c,
                              modules: c.modules.map((q) =>
                                q.id === m.id
                                  ? { ...q, yaw: Number(e.target.value) }
                                  : q,
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        Height (m)
                        <input
                          type="number"
                          value={m.height}
                          min="0"
                          max="5"
                          step=".1"
                          onChange={(e) =>
                            setCfg((c) => ({
                              ...c,
                              modules: c.modules.map((q) =>
                                q.id === m.id
                                  ? { ...q, height: Number(e.target.value) }
                                  : q,
                              ),
                            }))
                          }
                        />
                      </label>
                    </div>
                    <button
                      className="delete-device"
                      onClick={async () => {
                        if (
                          !window.confirm(
                            `Delete ${m.name} from this home? Its connection will close. Saved recordings and activity history will remain.`,
                          )
                        )
                          return;
                        try {
                          await api("/api/disconnect", { moduleId: m.id });
                          const modules = cfg.modules.filter(
                            (q) => q.id !== m.id,
                          );
                          const next = {
                            ...cfg,
                            modules,
                            activeModuleId:
                              cfg.activeModuleId === m.id
                                ? modules[0]?.id
                                : cfg.activeModuleId,
                          };
                          await api("/api/home", next);
                          setCfg(next);
                          setEditingSensor(null);
                          if (placing === m.id) setPlacing(null);
                          setWifiKey(null);
                          setMessage("Device removed from this home.");
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      Delete this device
                    </button>
                    <button onClick={() => setEditingSensor(null)}>
                      Close details
                    </button>
                  </div>
                ))}
            </section>
          </>
        )}
        <footer>
          <span>Haven · Local sensing demo</span>
          <span>Motion signals are experimental; not for health or safety decisions.</span>
        </footer>
      </main>
      {dialog && (
        <div className="modal-backdrop" onClick={() => setDialog(null)}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={"Add " + dialog}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-heading">
              <h2>Add {dialog}</h2>
              <button aria-label="Close dialog" onClick={() => setDialog(null)}>
                ×
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (dialog === "room") submitRoom(e.currentTarget);
                if (dialog === "module") submitModule(e.currentTarget);
              }}
            >
              <label>
                Name
                <input
                  name="name"
                  required
                  maxLength={80}
                  placeholder={dialog === "room" ? "Bedroom" : "Radar 02"}
                />
              </label>
              {dialog === "room" && (
                <div className="form-grid">
                  {["x", "z", "width", "depth"].map((k) => (
                    <label key={k}>
                      {k === "z"
                        ? "Y"
                        : k === "yaw"
                          ? "Facing direction (°)"
                          : k}{" "}
                      (m)
                      <input
                        name={k}
                        type="number"
                        min={k === "width" || k === "depth" ? 0.1 : -50}
                        max="100"
                        required
                        defaultValue={
                          k === "width"
                            ? footprint &&
                              !mappedRooms.some((r) => !r.scanEnvelope)
                              ? footprint.width
                              : 4
                            : k === "depth"
                              ? footprint &&
                                !mappedRooms.some((r) => !r.scanEnvelope)
                                ? footprint.depth
                                : 4
                              : 0
                        }
                        step="any"
                      />
                    </label>
                  ))}
                </div>
              )}
              {dialog === "module" && (
                <>
                  {scan ? (
                    <p className="muted small">
                      Save this module, then tap its installed position on your
                      scan. The room and map coordinates will come from that
                      position.
                    </p>
                  ) : (
                    <label>
                      Room
                      <select name="room">
                        {cfg.rooms.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <div className="form-grid">
                    {(scan
                      ? ["height", "yaw"]
                      : ["x", "z", "height", "yaw"]
                    ).map((k) => (
                      <label key={k}>
                        {k === "z" ? "Y" : k}
                        <input
                          name={k}
                          type="number"
                          min={k === "height" ? 0 : -360}
                          max="360"
                          step=".1"
                          required
                          defaultValue={k === "height" ? 1.2 : 0}
                        />
                      </label>
                    ))}
                  </div>
                  <label>
                    Serial port
                    <input name="port" defaultValue={port} />
                  </label>
                </>
              )}
              <button className="primary">
                <Plus size={16} />
                Save {dialog}
              </button>
            </form>
          </section>
        </div>
      )}
      {showServerSetup && (
        <ServerSetup
          onConfigured={() => {
            setShowServerSetup(false);
            setError("");
            window.location.reload();
          }}
        />
      )}
    </div>
  );
}
function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
