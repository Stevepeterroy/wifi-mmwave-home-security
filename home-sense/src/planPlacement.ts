import type { Config, Module, Room } from "./domain";
import { inRoom } from "./domain";
import { homePlanBounds, scanRooms } from "./planProjection";
import type { ScanFootprint } from "./planProjection";

export type PlacementScan = {
  id: string;
  scale: number;
  upAxis?: "Y" | "Z";
  yaw?: number;
};
export function scanAlignment(scan: PlacementScan) {
  return { scale: scan.scale, upAxis: scan.upAxis || "Y", yaw: scan.yaw || 0 };
}
export function scanModules(
  modules: Module[],
  rooms: Room[],
  scan: PlacementScan,
  footprint: ScanFootprint,
) {
  const area = { x: 0, z: 0, ...footprint };
  const alignment = scanAlignment(scan);
  return modules.filter((m) => {
    const room = rooms.find((r) => r.id === m.roomId);
    const associated = m.planModelId
      ? m.planModelId === scan.id
      : !!room &&
        (room.planModelId === scan.id ||
          (!room.planModelId && room.modelId === scan.id));
    // Legacy placements have no saved alignment and belong only to the default scan frame.
    const placed = m.scanAlignment || { scale: 1, upAxis: "Y", yaw: 0 };
    return (
      associated &&
      inRoom(m, area) &&
      [m.x, m.z, m.height, m.yaw].every(Number.isFinite) &&
      placed.scale === alignment.scale &&
      placed.upAxis === alignment.upAxis &&
      placed.yaw === alignment.yaw
    );
  });
}
export function syncScanEnvelope(
  rooms: Room[],
  scan: PlacementScan,
  footprint: ScanFootprint,
) {
  let changed = false;
  const result = rooms.map((r) => {
    if (!r.scanEnvelope || r.planModelId !== scan.id) return r;
    if (
      r.x === 0 &&
      r.z === 0 &&
      r.width === footprint.width &&
      r.depth === footprint.depth
    )
      return r;
    changed = true;
    return { ...r, x: 0, z: 0, width: footprint.width, depth: footprint.depth };
  });
  return changed ? result : rooms;
}
export function placeModule(
  config: Config,
  moduleId: string,
  point: { x: number; z: number },
  scan?: PlacementScan,
  footprint?: ScanFootprint,
): Config {
  if (!config.modules.some((m) => m.id === moduleId))
    throw Error("Choose a registered module.");
  if (![point.x, point.z].every(Number.isFinite))
    throw Error("Choose a valid position on the map.");
  let rooms = config.rooms;
  let candidates: Room[];
  if (scan) {
    if (!footprint)
      throw Error(
        "Wait for the scan to finish processing before placing a sensor.",
      );
    const bounds = homePlanBounds(rooms, footprint);
    const area = { x: 0, z: 0, ...footprint };
    if (!inRoom(point, area))
      throw Error("Place the sensor inside the scanned footprint.");
    rooms = syncScanEnvelope(rooms, scan, footprint);
    candidates = scanRooms(rooms, scan.id, bounds);
    if (!candidates.length) {
      if (footprint.width > 100 || footprint.depth > 100)
        throw Error(
          "Mark individual rooms in this large scan before placing sensors.",
        );
      const id = "scan:" + scan.id;
      if (rooms.some((r) => r.id === id))
        throw Error(
          "Review the existing scanned-space boundary before placing a sensor.",
        );
      const areaRoom: Room = {
        id,
        name: "Scanned space",
        x: 0,
        z: 0,
        width: footprint.width,
        depth: footprint.depth,
        care: false,
        modelId: scan.id,
        planModelId: scan.id,
        scanEnvelope: true,
      };
      rooms = [...rooms, areaRoom];
      candidates = [areaRoom];
    }
  } else candidates = rooms;
  const containing = candidates.filter((r) => inRoom(point, r));
  if (containing.length > 1)
    throw Error(
      "Room boundaries overlap here. Adjust them before assigning the sensor.",
    );
  if (!containing.length)
    throw Error("Mark a room around this location before placing the sensor.");
  const room = containing[0];
  // Rounding near an edge must not move a valid tap into a different room.
  const coordinate = (v: number, min: number, size: number) =>
    Math.max(
      min,
      Math.min(
        min + size - Math.min(1e-6, size / 2),
        Math.round(v * 100) / 100,
      ),
    );
  return {
    ...config,
    rooms,
    modules: config.modules.map((m) =>
      m.id !== moduleId
        ? m
        : {
            ...m,
            x: coordinate(point.x, room.x, room.width),
            z: coordinate(point.z, room.z, room.depth),
            roomId: room.id,
            planModelId: scan?.id,
            scanAlignment: scan ? scanAlignment(scan) : undefined,
          },
    ),
  };
}

/** Unplace a sensor without changing identity, pairing or saved recordings. */
export function removeModulePlacement(config: Config, moduleId: string): Config {
  if (!config.modules.some(m => m.id === moduleId)) throw Error("Choose a registered module.");
  return {...config, modules: config.modules.map(m => m.id !== moduleId ? m : {
    ...m, roomId: "", planModelId: undefined, scanAlignment: undefined,
  })};
}
