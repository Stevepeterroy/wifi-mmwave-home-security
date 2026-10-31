import { it, expect, vi } from "vitest";
import * as THREE from "three";
import { disposeObject } from "./sceneResources";
it("releases shared scan geometry, materials and texture allocations once", () => {
  const texture = new THREE.Texture();
  const material = new THREE.MeshStandardMaterial({ map: texture });
  const geometry = new THREE.BoxGeometry();
  const root = new THREE.Group();
  root.add(
    new THREE.Mesh(geometry, material),
    new THREE.Mesh(geometry, material),
  );
  const g = vi.spyOn(geometry, "dispose"),
    m = vi.spyOn(material, "dispose"),
    t = vi.spyOn(texture, "dispose");
  disposeObject(root);
  expect(g).toHaveBeenCalledTimes(1);
  expect(m).toHaveBeenCalledTimes(1);
  expect(t).toHaveBeenCalledTimes(1);
});
