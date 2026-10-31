import { containsPoint, roomsOverlap } from "./roomBoundary";
import type { Config, Room } from "./domain";
export function drawnRoom(
  a: { x: number; z: number },
  b: { x: number; z: number },
  extent: { width: number; depth: number },
) {
  if (![a.x, a.z, b.x, b.z, extent.width, extent.depth].every(Number.isFinite))
    throw Error("Invalid room boundary.");
  const clamp = (v: number, max: number) => Math.max(0, Math.min(max, v));
  const x = clamp(Math.min(a.x, b.x), extent.width),
    z = clamp(Math.min(a.z, b.z), extent.depth);
  const width = clamp(Math.max(a.x, b.x), extent.width) - x,
    depth = clamp(Math.max(a.z, b.z), extent.depth) - z;
  if (width < 0.2 || depth < 0.2)
    throw Error("Draw a room at least 20 cm wide and deep.");
  return { x, z, width, depth };
}
export function partitionScan(
  config: Config,
  scanId: string,
  rooms: Room[],
): Config {
  if (!rooms.length || rooms.some((r) => !r.name.trim()))
    throw Error("Draw and name your rooms first.");
  for (let i = 0; i < rooms.length; i++)
    for (let j = i + 1; j < rooms.length; j++) {
      const a = rooms[i],
        b = rooms[j];
      if (roomsOverlap(a, b))
        throw Error("Rooms overlap. Remove or redraw the overlapping section.");
    }
  const belongs = (r: Room) =>
    r.planModelId === scanId || (!r.planModelId && r.modelId === scanId);
  const removed = new Set(config.rooms.filter(belongs).map((r) => r.id));
  return {
    ...config,
    rooms: [
      ...config.rooms.filter((r) => !belongs(r)),
      ...rooms.map((r) => ({
        ...r,
        name: r.name.trim(),
        planModelId: scanId,
        modelId: scanId,
        scanEnvelope: false,
      })),
    ],
    modules: config.modules.map((m) => {
      if (m.planModelId !== scanId && !removed.has(m.roomId)) return m;
      const matches = rooms.filter((r) => containsPoint(m, r));
      return { ...m, roomId: matches.length === 1 ? matches[0].id : "" };
    }),
  };
}

export function savedScanRooms(config: Config, scanId: string): Room[] {
  return config.rooms
    .filter(
      (r) =>
        r.boundary &&
        r.boundary.length >= 3 &&
        (r.planModelId === scanId || (!r.planModelId && r.modelId === scanId)),
    )
    .map((r) => ({ ...r, boundary: r.boundary!.map((p) => ({ ...p })) }));
}
export function replaceDrawnRoom(rooms: Room[], room: Room): Room[] {
  const index = rooms.findIndex((r) => r.id === room.id);
  return index < 0
    ? [...rooms, room]
    : rooms.map((r) => (r.id === room.id ? room : r));
}
