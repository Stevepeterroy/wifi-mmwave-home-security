import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { prepareScanSurface } from "./scanSurface";

function triangle() {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute([0, 0, 0, 1, 0, 0, 0, 1, 0], 3),
  );
  geometry.setIndex([0, 1, 2]);
  return geometry;
}
describe("imported scan lighting", () => {
  it("generates lighting normals for a GLB with only positions and UVs", () => {
    const geometry = triangle();
    prepareScanSurface(geometry);
    const normal = geometry.getAttribute("normal");
    for (let i = 0; i < 3; i++) expect(normal.getZ(i)).toBeCloseTo(1);
  });
  it("repairs zero or nonfinite exported normals", () => {
    const geometry = triangle();
    geometry.setAttribute(
      "normal",
      new THREE.Float32BufferAttribute([NaN, 0, 0, 0, 0, 0, 0, 0, 0], 3),
    );
    prepareScanSurface(geometry);
    expect(geometry.getAttribute("normal").getZ(0)).toBe(1);
  });
  it("preserves valid imported normals", () => {
    const geometry = triangle();
    geometry.computeVertexNormals();
    const normals = geometry.getAttribute("normal");
    prepareScanSurface(geometry);
    expect(geometry.getAttribute("normal")).toBe(normals);
  });
});
