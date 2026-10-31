import { it, expect } from "vitest";
import * as THREE from "three";
import { alignModel } from "./modelAlignment";
it("converts Z-up scans to metre-scale Y-up without changing source rotation", () => {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 4, 6));
  mesh.position.set(5, 6, 7);
  const aligned = alignModel(mesh, { scale: 0.5, upAxis: "Z" }),
    bounds = new THREE.Box3().setFromObject(aligned),
    size = bounds.getSize(new THREE.Vector3());
  expect(size.x).toBeCloseTo(1);
  expect(size.y).toBeCloseTo(3);
  expect(size.z).toBeCloseTo(2);
  expect(bounds.min.length()).toBeCloseTo(0);
  expect(mesh.rotation.x).toBe(0);
});
it("applies floor rotation and normalizes the resulting bounds", () => {
  const aligned = alignModel(new THREE.Mesh(new THREE.BoxGeometry(2, 3, 4)), {
      scale: 1,
      upAxis: "Y",
      yaw: 90,
    }),
    bounds = new THREE.Box3().setFromObject(aligned),
    size = bounds.getSize(new THREE.Vector3());
  expect(size.x).toBeCloseTo(4);
  expect(size.z).toBeCloseTo(2);
  expect(size.y).toBeCloseTo(3);
  expect(bounds.min.length()).toBeCloseTo(0);
});
it("rejects empty geometry instead of displaying an empty imported house", () => {
  expect(() => alignModel(new THREE.Group(), { scale: 1 })).toThrow();
});
