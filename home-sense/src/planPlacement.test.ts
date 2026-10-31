import { describe, it, expect } from "vitest";
import { initialConfig, inRoom, MultiTracker } from "./domain";
import { placeModule, removeModulePlacement, scanModules, syncScanEnvelope } from "./planPlacement";
import { homePlanBounds, scanRooms } from "./planProjection";
import type { Room } from "./domain";

const scan = { id: "fixture-scan", scale: 1 };
const footprint = {
  width: 3.32825779914856,
  depth: 4.307100772857666,
  height: 1.686529517173767,
};
const base = structuredClone(initialConfig);
base.rooms[0].modelId = scan.id;
const moduleId = base.modules[0].id;
const room = (id: string, x: number, width: number): Room => ({
  id,
  name: id,
  x,
  z: 0,
  width,
  depth: 4,
  care: false,
  planModelId: scan.id,
});

describe("placement on the active scanned space", () => {
  it("uses actual scan bounds instead of an overlapping example rectangle, preserves old rooms and persists on reload", () => {
    const before = structuredClone(base);
    const next = placeModule(
      base,
      moduleId,
      { x: 1.6, z: 4.2 },
      scan,
      footprint,
    );
    const assigned = next.modules[0];
    expect(assigned.roomId).toBe("scan:" + scan.id);
    expect(assigned.planModelId).toBe(scan.id);
    expect(assigned.scanAlignment).toEqual({ scale: 1, upAxis: "Y", yaw: 0 });
    expect(base).toEqual(before);
    expect(next.rooms.slice(0, base.rooms.length)).toEqual(base.rooms);
    const space = next.rooms.find((r) => r.id === assigned.roomId)!;
    expect(space.name).toBe("Scanned space");
    expect(space.width).toBe(footprint.width);
    expect(space.depth).toBe(footprint.depth);
    const restored = JSON.parse(JSON.stringify(next));
    expect(
      scanModules(restored.modules, restored.rooms, scan, footprint).map(
        (m) => m.id,
      ),
    ).toEqual([moduleId]);
    expect(
      scanRooms(
        restored.rooms,
        scan.id,
        homePlanBounds(restored.rooms, footprint),
      ),
    ).toEqual([space]);
  });
  it("refuses waiting, nonfinite and out-of-scan taps, even inside a stale example room", () => {
    expect(() => placeModule(base, moduleId, { x: 1, z: 1 }, scan)).toThrow(
      /processing/,
    );
    for (const point of [
      { x: 4, z: 1 },
      { x: 1, z: 5 },
      { x: -0.1, z: 1 },
      { x: NaN, z: 1 },
    ])
      expect(() =>
        placeModule(base, moduleId, point, scan, footprint),
      ).toThrow();
    expect(() =>
      placeModule(base, "unknown", { x: 1, z: 1 }, scan, footprint),
    ).toThrow(/registered/);
  });
  it("uses only active scan rooms, rejects gaps and overlapping boundaries", () => {
    const cfg = {
      ...base,
      rooms: [...base.rooms, room("actual-A", 0, 1.5), room("actual-B", 2, 1)],
    };
    expect(
      placeModule(cfg, moduleId, { x: 2.5, z: 2 }, scan, footprint).modules[0]
        .roomId,
    ).toBe("actual-B");
    expect(() =>
      placeModule(cfg, moduleId, { x: 1.8, z: 2 }, scan, footprint),
    ).toThrow(/Mark a room/);
    expect(() =>
      placeModule(
        { ...cfg, rooms: [...cfg.rooms, room("overlap", 1, 2)] },
        moduleId,
        { x: 2.5, z: 2 },
        scan,
        footprint,
      ),
    ).toThrow(/overlap/);
  });
  it("does not carry sensor positions across scans or changed alignment and accepts a new reviewed placement", () => {
    const placed = placeModule(base, moduleId, { x: 1, z: 1 }, scan, footprint);
    const other = { ...scan, id: "another-scan" };
    expect(scanModules(placed.modules, placed.rooms, other, footprint)).toEqual(
      [],
    );
    for (const changed of [
      { ...scan, scale: 2 },
      { ...scan, yaw: 90 },
      { ...scan, upAxis: "Z" as const },
    ]) {
      expect(
        scanModules(placed.modules, placed.rooms, changed, footprint),
      ).toEqual([]);
      const rePlaced = placeModule(
        placed,
        moduleId,
        { x: 1, z: 1 },
        changed,
        footprint,
      );
      expect(
        scanModules(rePlaced.modules, rePlaced.rooms, changed, footprint),
      ).toHaveLength(1);
    }
    // Existing default-alignment placements remain usable only for their associated scan.
    expect(scanModules(base.modules, base.rooms, scan, footprint)).toHaveLength(
      1,
    );
    expect(scanModules(base.modules, base.rooms, other, footprint)).toEqual([]);
  });
  it("updates a generated extent with the GLB while named room regions replace its overlay", () => {
    const placed = placeModule(base, moduleId, { x: 1, z: 1 }, scan, footprint);
    expect(syncScanEnvelope(placed.rooms, scan, footprint)).toBe(placed.rooms);
    const changed = { width: 6, depth: 8, height: 2 };
    const rooms = syncScanEnvelope(placed.rooms, scan, changed);
    expect(rooms.find((r) => r.scanEnvelope)!.width).toBe(6);
    expect(rooms[0]).toBe(placed.rooms[0]);
    const defined = [...placed.rooms, room("named-part", 0, 2)];
    expect(
      scanRooms(defined, scan.id, homePlanBounds(defined, footprint)).map(
        (r) => r.id,
      ),
    ).toEqual(["named-part"]);
    expect(
      placeModule(
        { ...placed, rooms: defined },
        moduleId,
        { x: 1, z: 1 },
        scan,
        footprint,
      ).modules[0].roomId,
    ).toBe("named-part");
  });
  it("keeps edge rounding inside the chosen room and foreign module tracks out of this plan", () => {
    const cfg = { ...base, rooms: [room("first", 0, 1), room("next", 1, 1)] };
    const placed = placeModule(
      cfg,
      moduleId,
      { x: 0.9999, z: 1 },
      scan,
      footprint,
    );
    expect(placed.modules[0].roomId).toBe("first");
    expect(inRoom(placed.modules[0], cfg.rooms[0])).toBe(true);
    const modules = scanModules(
      placed.modules,
      placed.rooms,
      { ...scan, id: "foreign-scan" },
      footprint,
    );
    const tracker = new MultiTracker();
    const frame = {
      sequence: 1,
      received_at: 100,
      reported_points: 2,
      preview_incomplete: false,
      points: [
        { point_index: 1, x_cm: 1, y_cm: 100, z_cm: 0, velocity_cm_s: 100 },
        { point_index: 2, x_cm: 2, y_cm: 100, z_cm: 0, velocity_cm_s: 100 },
      ],
    };
    expect(
      tracker.update(
        modules,
        {
          [moduleId]: {
            connected: true,
            radar_verified: true,
            last_frame: frame,
          },
        },
        100,
      ),
    ).toEqual([]);
  });
});

it("unplaces radar without deleting registration or history, then permits replacement", () => {
 const placed = placeModule(base, moduleId, {x:1,z:1}, scan, footprint);
 const removed = removeModulePlacement(placed, moduleId);
 expect(removed.modules.length).toBe(placed.modules.length);
 expect(removed.modules[0].id).toBe(moduleId);
 expect(removed.modules[0].roomId).toBe("");
 expect(removed.events).toEqual(placed.events);
 expect(removed.rooms).toEqual(placed.rooms);
 expect(scanModules(removed.modules,removed.rooms,scan,footprint)).toHaveLength(0);
 const replaced = placeModule(removed,moduleId,{x:1,z:1},scan,footprint);
 expect(scanModules(replaced.modules,replaced.rooms,scan,footprint)).toHaveLength(1);
 expect(() => removeModulePlacement(base,"unknown")).toThrow();
});
