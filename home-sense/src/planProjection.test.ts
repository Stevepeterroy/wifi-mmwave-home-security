import { it, expect } from "vitest";
import * as THREE from "three";
import {
  planFrustum,
  PLAN_MARGIN,
  roomBounds,
  planViewBox,
  homePlanBounds,
  scanRooms,
} from "./planProjection";
it("maps model floor coordinates to the same pixels as padded SVG in wide and narrow layouts", () => {
  for (const [w, h] of [
    [800, 450],
    [300, 600],
    [400, 400],
  ]) {
    const width = 8,
      depth = 6,
      f = planFrustum(width, depth, w, h);
    const camera = new THREE.OrthographicCamera(
      f.left,
      f.right,
      f.top,
      f.bottom,
      0.01,
      200,
    );
    camera.position.set(width / 2, 40, depth / 2);
    camera.up.set(0, 0, -1);
    camera.lookAt(width / 2, 0, depth / 2);
    camera.updateMatrixWorld();
    const scale = Math.min(
      w / (width + 2 * PLAN_MARGIN),
      h / (depth + 2 * PLAN_MARGIN),
    );
    const padX = (w - (width + 2 * PLAN_MARGIN) * scale) / 2,
      padY = (h - (depth + 2 * PLAN_MARGIN) * scale) / 2;
    for (const [x, z] of [
      [0, 0],
      [8, 6],
      [2, 4],
    ]) {
      const projected = new THREE.Vector3(x, 0, z).project(camera);
      expect(((projected.x + 1) * w) / 2).toBeCloseTo(
        padX + (x + PLAN_MARGIN) * scale,
        6,
      );
      expect(((1 - projected.y) * h) / 2).toBeCloseTo(
        padY + (z + PLAN_MARGIN) * scale,
        6,
      );
    }
  }
});

it("fits the active scan independently of the old example rooms and follows new scan dimensions", () => {
  const examples = [{ x: 0, z: 0, width: 9, depth: 7 }];
  expect(homePlanBounds(examples)).toEqual(roomBounds(examples));
  const bounds = homePlanBounds(examples, {
    width: 3.3,
    depth: 4.3,
    height: 1.7,
  });
  expect(bounds).toEqual({
    minX: 0,
    minZ: 0,
    width: 3.3,
    depth: 4.3,
    centerX: 1.65,
    centerZ: 2.15,
  });
  expect(
    homePlanBounds(examples, { width: 12, depth: 2, height: 3 }).width,
  ).toBe(12);
  expect(() =>
    homePlanBounds(examples, { width: NaN, depth: 4, height: 2 }),
  ).toThrow();
});

it("keeps only room labels assigned to this scan and inside its footprint", () => {
  const bounds = homePlanBounds([], { width: 3, depth: 4, height: 2 });
  const inside = { x: 0, z: 0, width: 2, depth: 3 };
  const linked = { ...inside, planModelId: "current" };
  const legacyLinked = { ...inside, modelId: "current" };
  expect(
    scanRooms(
      [
        inside,
        linked,
        legacyLinked,
        { ...linked, width: 5 },
        { ...linked, x: -1 },
        { ...linked, planModelId: "old", modelId: "current" },
      ],
      "current",
      bounds,
    ),
  ).toEqual([linked, legacyLinked]);
  expect(scanRooms([linked], "replacement", bounds)).toEqual([]);
});

it("includes rooms on both sides of the origin and shares the shifted plan rectangle", () => {
  const bounds = roomBounds([
    { x: -5, z: -3, width: 4, depth: 2 },
    { x: 2, z: 1, width: 3, depth: 4 },
  ]);
  expect(bounds).toEqual({
    minX: -5,
    minZ: -3,
    width: 10,
    depth: 8,
    centerX: 0,
    centerZ: 1,
  });
  expect(
    planViewBox(bounds.width, bounds.depth, bounds.minX, bounds.minZ),
  ).toBe("-5.3 -3.3 10.6 8.6");
  const f = planFrustum(bounds.width, bounds.depth, 500, 400),
    camera = new THREE.OrthographicCamera(
      f.left,
      f.right,
      f.top,
      f.bottom,
      0.01,
      200,
    );
  camera.position.set(bounds.centerX, 40, bounds.centerZ);
  camera.up.set(0, 0, -1);
  camera.lookAt(bounds.centerX, 0, bounds.centerZ);
  camera.updateMatrixWorld();
  const corner = new THREE.Vector3(-5, 0, -3).project(camera),
    scale = Math.min(500 / 10.6, 400 / 8.6);
  expect((corner.x + 1) * 250).toBeCloseTo(
    (500 - 10.6 * scale) / 2 + 0.3 * scale,
    6,
  );
  expect((1 - corner.y) * 200).toBeCloseTo(
    (400 - 8.6 * scale) / 2 + 0.3 * scale,
    6,
  );
});
