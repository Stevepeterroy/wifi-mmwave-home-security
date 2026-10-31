import { expect, it } from "vitest";
import { drawnRoom, partitionScan } from "./roomPartition";
import { initialConfig } from "./domain";
it("draws in either direction and clamps to the actual scan", () => {
  expect(
    drawnRoom({ x: 5, z: 4 }, { x: 0, z: 0 }, { width: 4, depth: 3 }),
  ).toEqual({ x: 0, z: 0, width: 4, depth: 3 });
  expect(() =>
    drawnRoom({ x: 1, z: 1 }, { x: 1.01, z: 2 }, { width: 4, depth: 3 }),
  ).toThrow();
});
it("splits a shared scan into named adjoining rooms and retains sensor poses", () => {
  const config = structuredClone(initialConfig);
  config.rooms = [
    {
      id: "old",
      name: "Whole scan",
      x: 0,
      z: 0,
      width: 4,
      depth: 3,
      care: false,
      modelId: "scan",
    },
  ];
  config.modules = [
    {
      id: "sensor",
      name: "Radar",
      roomId: "old",
      x: 3,
      z: 1,
      height: 1.2,
      yaw: 90,
      port: "",
    },
  ];
  const rooms = [
    {
      id: "a",
      name: "Living room",
      x: 0,
      z: 0,
      width: 2,
      depth: 3,
      care: false,
    },
    { id: "b", name: "Bedroom", x: 2, z: 0, width: 2, depth: 3, care: false },
  ];
  const next = partitionScan(config, "scan", rooms);
  expect(next.rooms.map((r) => r.name)).toEqual(["Living room", "Bedroom"]);
  expect(next.modules[0]).toEqual({ ...config.modules[0], roomId: "b" });
  expect(
    next.rooms.every((r) => r.modelId === "scan" && r.planModelId === "scan"),
  ).toBe(true);
  expect(config.rooms[0].id).toBe("old");
  expect(() =>
    partitionScan(config, "scan", [rooms[0], { ...rooms[1], x: 1 }]),
  ).toThrow("overlap");
});

import { savedScanRooms, replaceDrawnRoom } from "./roomPartition";
it("reloads saved outlines and replaces a redrawn room without deleting its neighbour", () => {
  const config = structuredClone(initialConfig);
  config.rooms = [
    {
      id: "a",
      name: "Living",
      x: 0,
      z: 0,
      width: 1,
      depth: 1,
      care: true,
      planModelId: "scan",
      boundary: [
        { x: 0, z: 0 },
        { x: 1, z: 0 },
        { x: 0, z: 1 },
      ],
    },
    {
      id: "b",
      name: "Bedroom",
      x: 1,
      z: 0,
      width: 1,
      depth: 1,
      care: false,
      planModelId: "scan",
      boundary: [
        { x: 1, z: 0 },
        { x: 2, z: 0 },
        { x: 1, z: 1 },
      ],
    },
  ];
  const draft = savedScanRooms(config, "scan");
  draft[0].boundary![0].x = 0.1;
  expect(config.rooms[0].boundary![0].x).toBe(0);
  const next = replaceDrawnRoom(draft, { ...draft[0], name: "Edited" });
  expect(next.map((r) => r.id)).toEqual(["a", "b"]);
  expect(next[0].care).toBe(true);
  expect(next[1].name).toBe("Bedroom");
  expect(savedScanRooms(config, "other")).toEqual([]);
});
