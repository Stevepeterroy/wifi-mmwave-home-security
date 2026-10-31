import * as THREE from "three";

/** Scan exports can omit normals; lit materials then render as black silhouettes. */
export function prepareScanSurface(geometry: THREE.BufferGeometry) {
  const normals = geometry.getAttribute("normal");
  const positions = geometry.getAttribute("position");
  let valid = !!normals && normals.count === positions?.count;
  if (normals && valid) {
    for (let i = 0; i < normals.count; i++) {
      const x = normals.getX(i),
        y = normals.getY(i),
        z = normals.getZ(i);
      if (!Number.isFinite(x + y + z) || x * x + y * y + z * z < 1e-12) {
        valid = false;
        break;
      }
    }
  }
  if (!valid) {
    geometry.deleteAttribute("normal");
    geometry.computeVertexNormals();
  }
}
