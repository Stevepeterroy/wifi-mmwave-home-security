import { it, expect } from "vitest";
import * as THREE from "three";
import {
  roomSceneContext,
  roomTrailSegments,
  sensorMarkerPosition,
} from "./roomScene";
import { alignModel } from "./modelAlignment";
import type { Room, Module } from "./domain";
import type { ModelAsset } from "./assets";

const home: ModelAsset = {
  id: "home",
  name: "fixture-home.glb",
  scale: 1,
  files: [],
  created: "fixture",
};
const separate: ModelAsset = {
  ...home,
  id: "room-model",
  name: "fixture-room.glb",
};
const room: Room = {
  id: "r",
  name: "Fixture room",
  x: 5,
  z: 4,
  width: 3,
  depth: 3,
  care: false,
};
const sensor: Module = {
  id: "m",
  name: "Fixture sensor",
  roomId: room.id,
  x: 6,
  z: 5,
  height: 1.2,
  yaw: 0,
  port: "fixture",
};
const point = (x: number, z = 5) => ({ x, z, height: 1 });

it("keeps a shared home model in home coordinates when opening an offset room", () => {
  const assigned = { ...room, modelId: home.id };
  const context = roomSceneContext(assigned, [sensor], [home], home);
  expect(context.role).toBe("home");
  expect(context.modelOrigin).toBeUndefined();
  const geometry = alignModel(
    new THREE.Mesh(new THREE.BoxGeometry(10, 3, 8)),
    home,
    context.modelOrigin,
  );
  const bounds = new THREE.Box3().setFromObject(geometry);
  expect(bounds.min.toArray()).toEqual([0, 0, 0]);
  expect(bounds.getSize(new THREE.Vector3()).toArray()).toEqual([10, 3, 8]);
  expect(context.rooms).toEqual([assigned]);
});
it("puts a separate room model, sensor and observations in the same house frame without changing source geometry", () => {
  const assigned = { ...room, modelId: separate.id };
  const context = roomSceneContext(assigned, [sensor], [home, separate], home);
  expect(context.role).toBe("room");
  expect(context.modelOrigin).toEqual({ x: 5, z: 4 });
  const original = new THREE.Mesh(new THREE.BoxGeometry(3, 3, 3));
  const geometry = alignModel(original, separate, context.modelOrigin);
  const bounds = new THREE.Box3().setFromObject(geometry);
  expect(bounds.min.toArray()).toEqual([5, 0, 4]);
  expect(bounds.max.toArray()).toEqual([8, 3, 7]);
  const position = sensorMarkerPosition(sensor, false);
  expect(position.y).toBe(sensor.height);
  expect(
    bounds.containsPoint(new THREE.Vector3(position.x, position.y, position.z)),
  ).toBe(true);
  expect(bounds.containsPoint(new THREE.Vector3(6.5, 1, 5.5))).toBe(true);
  expect(original.position.toArray()).toEqual([0, 0, 0]);
});
it("shows only sensors inside the selected room and preserves source placements", () => {
  const outside = { ...sensor, id: "outside", x: 1, z: 1 };
  const otherRoomSensor = { ...sensor, id: "inside", roomId: "old-assignment" };
  const source = [sensor, outside, otherRoomSensor];
  const original = structuredClone(source);
  const context = roomSceneContext(room, source, [home], home);
  expect(context.modules.map((m) => m.id)).toEqual(["m", "inside"]);
  expect(source).toEqual(original);
});
it("names a missing room asset and uses an unshifted home or schematic fallback", () => {
  const assigned = { ...room, modelId: "missing-room" };
  const context = roomSceneContext(assigned, [sensor], [home], home);
  expect(context.missingRoomModel).toBe(true);
  expect(context.role).toBe("home");
  expect(context.model).toBe(home);
  expect(context.modelOrigin).toBeUndefined();
  const fallback = roomSceneContext(assigned, [sensor], []);
  expect(fallback.role).toBe("schematic");
  expect(fallback.model).toBeUndefined();
  expect(fallback.missingRoomModel).toBe(true);
});
it("keeps consecutive room trail runs separate instead of drawing a shortcut across an outside excursion", () => {
  const trail = [
    point(5.1),
    point(5.3),
    point(8.5),
    point(5.8),
    point(6.2),
    point(6.3),
  ];
  const before = structuredClone(trail);
  expect(roomTrailSegments(trail, room)).toEqual([
    trail.slice(0, 2),
    trail.slice(3),
  ]);
  expect(roomTrailSegments(trail)).toEqual([trail]);
  expect(trail).toEqual(before);
  expect(
    roomTrailSegments([point(5.1), point(NaN), point(6), point(6.2)], room),
  ).toEqual([[point(6), point(6.2)]]);
});
it("keeps plan symbols on the floor while 3D symbols use mounting height and rejects invalid model origins", () => {
  expect(sensorMarkerPosition(sensor, true)).toEqual({ x: 6, y: 0.1, z: 5 });
  expect(() =>
    alignModel(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1)), home, {
      x: NaN,
      z: 0,
    }),
  ).toThrow(/finite/);
});
