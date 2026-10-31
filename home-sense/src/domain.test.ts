import { describe, it, expect } from "vitest";
import {
  transform,
  clusters,
  Tracker,
  trialDue,
  reminderDates,
  calendarFile,
  inRoom,
  initialConfig,
  isCurrentTrack,
} from "./domain";
describe("sensor interpretation", () => {
  it("rotates radar metres into the placed room", () => {
    const p = transform(
      { point_index: 0, x_cm: 100, y_cm: 200, z_cm: -50, velocity_cm_s: -120 },
      { ...initialConfig.modules[0], x: 0, z: 0, yaw: 90 },
    );
    expect(p.x).toBeCloseTo(2);
    expect(p.z).toBeCloseTo(-1);
    expect(p.height).toBeCloseTo(0.7);
    expect(p.velocity).toBeCloseTo(-1.2);
  });
  it("groups density and rejects isolated reflections without claiming people", () => {
    expect(
      clusters([
        { x: 1, z: 1, height: 1, velocity: 0 },
        { x: 1.1, z: 1.1, height: 1, velocity: 0 },
        { x: 5, z: 5, height: 1, velocity: 0 },
      ]),
    ).toHaveLength(1);
  });
  it("matches each track once and resets after stale data", () => {
    const t = new Tracker(),
      p = { x: 1, z: 1, height: 1, velocity: 0 };
    const first = t.update([p], 1)[0].id;
    expect(t.update([{ ...p, x: 1.1 }], 1.2)[0].id).toBe(first);
    expect(t.tracks[0].age).toBe(2);
    expect(t.update([], 5)).toHaveLength(0);
  });
  it("keeps a recent map marker without counting it as current detection", () => {
    const t = new Tracker();
    t.update([{ x: 1, z: 1, height: 1, velocity: 0 }], 10);
    expect(t.update([], 10.2)[0].seen).toBe(10);
    expect(isCurrentTrack(t.update([], 10.5)[0], 10.5)).toBe(true);
    expect(isCurrentTrack(t.update([], 11)[0], 11)).toBe(false);
    expect(t.update([], 12.6)).toHaveLength(0);
  });
  it("reduces coordinate jitter for a matched reflection", () => {
    const t = new Tracker();
    t.update([{ x: 1, z: 1, height: 1, velocity: 0 }], 10);
    const next = t.update([{ x: 1.2, z: 1, height: 1, velocity: 0 }], 10.2)[0];
    expect(next.x).toBeCloseTo(1.13);
    expect(next.trail.at(-1)?.x).toBe(next.x);
  });
  it("assigns boundaries to only one adjoining room", () => {
    const p = { x: 5, z: 2 };
    expect(inRoom(p, initialConfig.rooms[0])).toBe(false);
    expect(inRoom(p, initialConfig.rooms[1])).toBe(true);
  });
});
describe("trial deadlines", () => {
  const t = {
    id: "t",
    name: "Polycam",
    start: "2026-10-08",
    days: 7,
    fee: 20,
    status: "Active Trial" as const,
    proof: "",
    repeatMinutes: 60,
  };
  it("calculates the buffer from expiry, not mistaken calendar days", () => {
    expect(reminderDates(t).map((d) => d.getDate())).toEqual([12, 13, 14]);
    expect(trialDue(t, new Date("2026-10-11T12:00:00"))).toBe(false);
    expect(trialDue(t, new Date("2026-10-12T12:00:00"))).toBe(true);
  });
  it("stops reminders only at verified cancellation", () => {
    expect(
      trialDue(
        { ...t, status: "Cancellation Pending" },
        new Date("2026-10-16"),
      ),
    ).toBe(true);
    expect(
      trialDue(
        { ...t, status: "Cancelled & Verified" },
        new Date("2026-10-16"),
      ),
    ).toBe(false);
  });
  it("exports three distinct priority calendar reminders", () => {
    const text = calendarFile(t);
    expect(text.match(/BEGIN:VEVENT/g)).toHaveLength(3);
    expect(text).toContain("DTSTART;VALUE=DATE:20261012");
    expect(text.match(/PRIORITY:1/g)).toHaveLength(3);
  });
});

import { MultiTracker } from "./domain";
describe("multi-room live sources", () => {
  it("filters outside reflections before clustering and expires held tracks on polling", () => {
    const t = new MultiTracker();
    const m = { ...initialConfig.modules[0], id: "a", x: 0, z: 0, yaw: 0 };
    const frame = { sequence: 1, received_at: 100, reported_points: 3, preview_incomplete: false,
      points: [90, 95, 110].map((x_cm, point_index) => ({ point_index, x_cm, y_cm: 50, z_cm: 0, velocity_cm_s: 0 })) };
    const nodes = { a: { connected: true, radar_verified: true, last_frame: frame } };
    const bounds = { minX: 0, minZ: 0, width: 1, depth: 1 };
    expect(t.update([m], nodes, 100, bounds)[0].x).toBeCloseTo(0.925);
    const empty = { a: { ...nodes.a, last_frame: { ...frame, sequence: 2, received_at: 100.2, points: [], reported_points: 0 } } };
    expect(t.update([m], empty, 100.2, bounds)).toHaveLength(1);
    expect(t.update([m], empty, 100.5, bounds)).toHaveLength(1);
    expect(t.update([m], empty, 102.3, bounds)).toHaveLength(1);
    expect(t.update([m], empty, 103, bounds)).toHaveLength(0);
  });
  it("keeps IDs, placement and freshness separate per node", () => {
    const t = new MultiTracker(),
      a = { ...initialConfig.modules[0], id: "a", x: 0, z: 0 },
      b = { ...a, id: "b", x: 5 };
    const frame = {
      sequence: 1,
      reported_points: 2,
      preview_incomplete: false,
      received_at: 100,
      points: [
        { point_index: 0, x_cm: 100, y_cm: 100, z_cm: 0, velocity_cm_s: 70 },
        { point_index: 1, x_cm: 110, y_cm: 100, z_cm: 0, velocity_cm_s: 70 },
      ],
    };
    const nodes = {
      a: { connected: true, radar_verified: true, last_frame: frame },
      b: { connected: true, radar_verified: true, last_frame: frame },
    };
    const groups = t.update([a, b], nodes, 100.2);
    expect(groups).toHaveLength(2);
    expect(groups[0].key).not.toBe(groups[1].key);
    expect(groups[1].x - groups[0].x).toBeCloseTo(5);
    expect(
      t.update(
        [a, b],
        { ...nodes, b: { ...nodes.b, connected: false } },
        100.4,
      ),
    ).toHaveLength(1);
    expect(t.update([a, b], nodes, 103)).toHaveLength(0);
  });
  it("recomputes an unchanged report when a sensor placement changes", () => {
    const t = new MultiTracker(),
      a = { ...initialConfig.modules[0], id: "a", x: 0, z: 0 };
    const frame = {
      sequence: 1,
      reported_points: 2,
      preview_incomplete: false,
      received_at: 100,
      points: [
        { point_index: 0, x_cm: 100, y_cm: 100, z_cm: 0, velocity_cm_s: 70 },
        { point_index: 1, x_cm: 110, y_cm: 100, z_cm: 0, velocity_cm_s: 70 },
      ],
    };
    const nodes = {
      a: { connected: true, radar_verified: true, last_frame: frame },
    };
    t.update([a], nodes, 100);
    expect(t.update([{ ...a, x: 3 }], nodes, 100.2)[0].x).toBeCloseTo(4.05);
  });
});
