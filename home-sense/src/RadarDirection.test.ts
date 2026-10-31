import { expect, it } from "vitest";
import { radarDirection } from "./RadarDirection";
it("uses the same facing convention as placement and defaults to 120 degrees", () => {
  const down = radarDirection({ x: 2, z: 3, yaw: 0 });
  expect(down.fov).toBe(120);
  expect(down.tip).toEqual({ x: 2, z: 11 });
  const right = radarDirection({ x: 2, z: 3, yaw: 90, fov: 90 });
  expect(right.tip.x).toBeCloseTo(10);
  expect(right.tip.z).toBeCloseTo(3);
  expect(right.fov).toBe(120);
  const up = radarDirection({ x: 2, z: 3, yaw: 180 });
  expect(up.tip.z).toBeCloseTo(-5);
});
it("keeps a fixed 120 degree view regardless of saved legacy angles", () => {
  expect(radarDirection({ x: 0, z: 0, yaw: 0, fov: NaN }).fov).toBe(120);
  expect(radarDirection({ x: 0, z: 0, yaw: 0, fov: 500 }).fov).toBe(120);
});

import { facingToward } from "./RadarDirection";
it("turns map pointer coordinates into heading without moving the sensor", () => {
  const origin = { x: 2, z: 3 };
  expect(facingToward(origin, { x: 2, z: 4 })).toBe(0);
  expect(facingToward(origin, { x: 3, z: 3 })).toBe(90);
  expect(facingToward(origin, { x: 2, z: 2 })).toBe(180);
  expect(facingToward(origin, { x: 1, z: 3 })).toBe(270);
  expect(facingToward(origin, origin)).toBeNull();
  expect(facingToward(origin, { x: NaN, z: 3 })).toBeNull();
  expect(origin).toEqual({ x: 2, z: 3 });
});

it("keeps the drag handle nearby while coverage remains eight metres", () => {
  const m = { x: 1, z: 2, yaw: 45 };
  const coverage = radarDirection(m),
    handle = radarDirection(m, 0.8);
  expect(Math.hypot(coverage.tip.x - m.x, coverage.tip.z - m.z)).toBeCloseTo(8);
  expect(Math.hypot(handle.tip.x - m.x, handle.tip.z - m.z)).toBeCloseTo(0.8);
});
