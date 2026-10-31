import { containsPoint } from "./roomBoundary";
export type Point = {
  point_index: number;
  x_cm: number;
  y_cm: number;
  z_cm: number;
  velocity_cm_s: number;
};
export type Frame = {
  sequence: number;
  reported_points: number;
  points: Point[];
  preview_incomplete: boolean;
  received_at?: number;
};
export type Room = {
  id: string;
  name: string;
  x: number;
  z: number;
  width: number;
  depth: number;
  care: boolean;
  modelId?: string;
  planModelId?: string;
  scanEnvelope?: boolean;
  boundary?: { x: number; z: number }[];
};
export type Module = {
  id: string;
  name: string;
  roomId: string;
  x: number;
  z: number;
  height: number;
  yaw: number;
  fov?: number;
  port: string;
  planModelId?: string;
  scanAlignment?: { scale: number; upAxis: "Y" | "Z"; yaw: number };
};
export type RouterPlacement = {
  scanExtent?: {width: number; depth: number};
  id: string;
  name: string;
  x: number;
  z: number;
  height: number;
  planModelId?: string;
  scanAlignment?: { scale: number; upAxis: "Y" | "Z"; yaw: number };
};
export type Trial = {
  id: string;
  name: string;
  start: string;
  days: number;
  fee: number;
  status: "Active Trial" | "Cancellation Pending" | "Cancelled & Verified";
  proof: string;
  repeatMinutes: number;
  timezone?: string;
};
export type Event = {
  moduleId?: string;
  scanSnapshot?: {scale:number;upAxis?:"Y"|"Z";yaw?:number;files?:{name:string;size:number;sha256:string}[]};
  modelId?: string;
  placement?: Module;
  status?: "open" | "closed";
  lastMotionAt?: string;
  endedAt?: string;
  stopReason?: string;
  samples?: {at: string; sequence: number; points: Point[]}[];
  sampleCount?: number;
  recordingTruncated?: boolean;
  partialConsolePreview?: boolean;
  id: string;
  at: string;
  room: string;
  kind: string;
  source: "live" | "recorded";
  acknowledged: boolean;
};
export type Config = {
  houseCare?: boolean;
  profile: string;
  homeName: string;
  homeModelId?: string;
  dataSource?: "recorded" | "live";
  activeModuleId?: string;
  rooms: Room[];
  modules: Module[];
  routers?: RouterPlacement[];
  away: boolean;
  events: Event[];
  trials: Trial[];
};
export const initialConfig: Config = {
  profile: "",
  homeName: "My home",
  away: false,
  events: [],
  trials: [],
  rooms: [
    {
      id: "living",
      name: "Living room",
      x: 0,
      z: 0,
      width: 5,
      depth: 4,
      care: false,
    },
    {
      id: "bedroom",
      name: "Bedroom",
      x: 5,
      z: 0,
      width: 4,
      depth: 4,
      care: true,
    },
    {
      id: "kitchen",
      name: "Kitchen",
      x: 0,
      z: 4,
      width: 5,
      depth: 3,
      care: false,
    },
    { id: "study", name: "Study", x: 5, z: 4, width: 4, depth: 3, care: false },
  ],
  modules: [
    {
      id: "rd60-1",
      name: "Radar 01",
      roomId: "living",
      x: 2.5,
      z: 0.4,
      height: 1.2,
      yaw: 0,
      port: "/dev/cu.usbserial-11320",
    },
  ],
};
export type WorldPoint = {
  x: number;
  z: number;
  height: number;
  velocity: number;
};
export function transform(p: Point, m: Module): WorldPoint {
  const a = (m.yaw * Math.PI) / 180,
    x = p.x_cm / 100,
    y = p.y_cm / 100;
  return {
    x: m.x + x * Math.cos(a) + y * Math.sin(a),
    z: m.z - x * Math.sin(a) + y * Math.cos(a),
    height: m.height + p.z_cm / 100,
    velocity: p.velocity_cm_s / 100,
  };
}
export function withinPlan(p: { x: number; z: number }, bounds: { minX: number; minZ: number; width: number; depth: number }) {
  return Number.isFinite(p.x) && Number.isFinite(p.z) &&
    p.x >= bounds.minX && p.x <= bounds.minX + bounds.width &&
    p.z >= bounds.minZ && p.z <= bounds.minZ + bounds.depth;
}
export function inRoom(
  p: { x: number; z: number },
  r: Pick<Room, "x" | "z" | "width" | "depth" | "boundary">,
) {
  return containsPoint(p, r);
}
export function clusters(
  points: WorldPoint[],
  eps = 0.65,
  minPoints = 2,
): WorldPoint[] {
  const labels = points.map(() => -1),
    visited = new Set<number>();
  let group = 0;
  const neighbours = (i: number) =>
    points
      .map((p, j) =>
        Math.hypot(p.x - points[i].x, p.z - points[i].z) <= eps ? j : -1,
      )
      .filter((j) => j >= 0);
  for (let i = 0; i < points.length; i++) {
    if (visited.has(i)) continue;
    visited.add(i);
    const ns = neighbours(i);
    if (ns.length < minPoints) continue;
    labels[i] = group;
    const todo = [...ns];
    for (let k = 0; k < todo.length; k++) {
      const j = todo[k];
      if (!visited.has(j)) {
        visited.add(j);
        const more = neighbours(j);
        if (more.length >= minPoints)
          for (const v of more) if (!todo.includes(v)) todo.push(v);
      }
      if (labels[j] < 0) labels[j] = group;
    }
    group++;
  }
  return Array.from({ length: group }, (_, g) => {
    const ps = points.filter((_, i) => labels[i] === g);
    return {
      x: ps.reduce((s, p) => s + p.x, 0) / ps.length,
      z: ps.reduce((s, p) => s + p.z, 0) / ps.length,
      height: ps.reduce((s, p) => s + p.height, 0) / ps.length,
      velocity: ps.reduce((s, p) => s + p.velocity, 0) / ps.length,
    };
  });
}
export type Track = WorldPoint & {
  key?: string;
  moduleId?: string;
  id: number;
  age: number;
  seen: number;
  trail: { x: number; z: number; height: number }[];
};
// Recent positions remain visible briefly on the map, but are not counted as current detections.
export const TRACK_DISPLAY_SECONDS = 2.5;
export const TRACK_CURRENT_SECONDS = 0.75;
export function isCurrentTrack(track: Track, now: number) {
  return now - track.seen <= TRACK_CURRENT_SECONDS;
}
export class Tracker {
  tracks: Track[] = [];
  next = 1;
  last = 0;
  reset() {
    this.tracks = [];
    this.next = 1;
    this.last = 0;
  }
  update(groups: WorldPoint[], time: number) {
    if (time < this.last || time - this.last > 2) this.reset();
    const old = this.tracks.filter((t) => time - t.seen <= TRACK_DISPLAY_SECONDS),
      used = new Set<number>();
    const matched = groups.map((p) => {
      const match = old
        .filter(
          (t) => !used.has(t.id) && Math.hypot(t.x - p.x, t.z - p.z) < 0.9,
        )
        .sort(
          (a, b) =>
            Math.hypot(a.x - p.x, a.z - p.z) - Math.hypot(b.x - p.x, b.z - p.z),
        )[0];
      if (match) {
        used.add(match.id);
        const filtered = { ...p, x: match.x * 0.35 + p.x * 0.65, z: match.z * 0.35 + p.z * 0.65 };
        return {
          ...filtered,
          id: match.id,
          age: match.age + 1,
          seen: time,
          trail: [...match.trail, filtered].slice(-15),
        };
      }
      return { ...p, id: this.next++, age: 1, seen: time, trail: [p] };
    });
    // A missed preview is not a new observation. Keep its original expiry.
    this.tracks = [...matched, ...old.filter((t) => !used.has(t.id) && time - t.seen <= TRACK_DISPLAY_SECONDS)];
    this.last = time;
    return this.tracks;
  }
}
const dayMs = 86400000;
export function expiry(t: Trial) {
  const d = new Date(t.start + "T00:00:00");
  d.setDate(d.getDate() + t.days);
  return d;
}
export function reminderDates(t: Trial) {
  const e = expiry(t);
  return [3, 2, 1].map((days) => {
    const d = new Date(e);
    d.setDate(d.getDate() - days);
    return d;
  });
}
export function trialDue(t: Trial, now = new Date()) {
  return t.status !== "Cancelled & Verified" && now >= reminderDates(t)[0];
}
function stamp(d: Date) {
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
}
function icsEscape(s: string) {
  return s
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;");
}
export function calendarFile(t: Trial) {
  return (
    [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Haven//Trial safeguards//EN",
      ...reminderDates(t).flatMap((d, i) => [
        "BEGIN:VEVENT",
        `UID:${t.id}-${i}@haven.local`,
        `DTSTAMP:${new Date()
          .toISOString()
          .replace(/[-:]/g, "")
          .replace(/\.\d{3}/, "")}`,
        `DTSTART;VALUE=DATE:${stamp(d)}`,
        `DTEND;VALUE=DATE:${stamp(new Date(d.getTime() + dayMs))}`,
        `SUMMARY:${icsEscape("HIGH PRIORITY: Cancel " + t.name + " trial")}`,
        "PRIORITY:1",
        `DESCRIPTION:${icsEscape("Verify cancellation before renewal. Renewal fee: " + t.fee + ". Import does not continuously sync; remove events after verification.")}`,
        "BEGIN:VALARM",
        "TRIGGER:-PT9H",
        "ACTION:DISPLAY",
        `DESCRIPTION:${icsEscape("Cancel " + t.name + " trial")}`,
        "END:VALARM",
        "END:VEVENT",
      ]),
      "END:VCALENDAR",
    ].join("\r\n") + "\r\n"
  );
}

export type NodeState = {
  connected: boolean;
  radar_verified: boolean;
  last_frame: Frame | null;
};
export class MultiTracker {
  private states = new Map<
    string,
    { tracker: Tracker; key: string; placement: string }
  >();
  reset() {
    this.states.clear();
  }
  update(
    modules: Module[],
    nodes: Record<string, NodeState>,
    now: number,
    bounds?: { minX: number; minZ: number; width: number; depth: number },
  ): Track[] {
    const output: Track[] = [];
    for (const m of modules) {
      let state = this.states.get(m.id);
      const placement = JSON.stringify([m.x, m.z, m.height, m.yaw, bounds]);
      if (!state || state.placement !== placement) {
        state = { tracker: new Tracker(), key: "", placement };
        this.states.set(m.id, state);
      }
      const node = nodes[m.id],
        frame = node?.last_frame;
      if (
        !node?.connected ||
        !node.radar_verified ||
        !frame ||
        !frame.received_at ||
        now - frame.received_at > TRACK_DISPLAY_SECONDS
      ) {
        state.tracker.reset();
        state.key = "";
        continue;
      }
      const key = frame.sequence + ":" + frame.received_at;
      if (state.key !== key) {
        state.tracker.update(
          clusters(frame.points.map((p) => transform(p, m)).filter((p) => !bounds || withinPlan(p, bounds))),
          frame.received_at,
        );
        state.key = key;
      }
      output.push(
        ...state.tracker.tracks.filter((t) => now - t.seen <= TRACK_DISPLAY_SECONDS).map((t) => ({
          ...t,
          moduleId: m.id,
          key: m.id + ":" + t.id,
        })),
      );
    }
    for (const key of this.states.keys())
      if (!modules.some((m) => m.id === key)) this.states.delete(key);
    return output;
  }
}
