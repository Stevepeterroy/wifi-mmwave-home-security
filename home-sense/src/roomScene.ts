import type { ModelAsset } from "./assets";
import { inRoom } from "./domain";
import type { Room, Module, Track } from "./domain";

export function sensorMarkerPosition(module: Module, plan: boolean) {
  return {
    x: module.x,
    y: plan ? 0.1 : Math.max(0.1, module.height),
    z: module.z,
  };
}

export function roomSceneContext(
  room: Room,
  modules: Module[],
  models: ModelAsset[],
  homeModel?: ModelAsset,
) {
  const assigned = models.find((model) => model.id === room.modelId);
  const separate = !!assigned && assigned.id !== homeModel?.id;
  const model = assigned || homeModel;
  return {
    model,
    modelOrigin: separate ? { x: room.x, z: room.z } : undefined,
    rooms: [room],
    modules: modules.filter((module) => inRoom(module, room)),
    role: separate ? "room" : model ? "home" : "schematic",
    missingRoomModel:
      !!room.modelId && !assigned && room.modelId !== homeModel?.id,
  };
}

/** Keep observed consecutive runs; never join across an excursion outside a room. */
export function roomTrailSegments(trail: Track["trail"], room?: Room) {
  const segments: Track["trail"][] = [];
  let run: Track["trail"] = [];
  for (const point of trail) {
    const valid = [point.x, point.z, point.height].every(Number.isFinite);
    if (valid && (!room || inRoom(point, room))) run.push(point);
    else {
      if (run.length > 1) segments.push(run);
      run = [];
    }
  }
  if (run.length > 1) segments.push(run);
  return segments;
}
