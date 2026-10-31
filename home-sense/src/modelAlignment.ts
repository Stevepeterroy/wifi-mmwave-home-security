import * as THREE from "three";
export function alignModel(
  object: THREE.Object3D,
  settings: { scale: number; upAxis?: "Y" | "Z"; yaw?: number },
  origin: { x: number; z: number } = { x: 0, z: 0 },
) {
  const root = new THREE.Group(),
    axis = new THREE.Group();
  root.add(axis);
  axis.add(object);
  root.scale.setScalar(settings.scale);
  root.rotation.y = ((settings.yaw || 0) * Math.PI) / 180;
  if (settings.upAxis === "Z") axis.rotation.x = -Math.PI / 2;
  const bounds = new THREE.Box3().setFromObject(root);
  if (
    bounds.isEmpty() ||
    ![...bounds.min.toArray(), ...bounds.max.toArray()].every(Number.isFinite)
  )
    throw Error("Scan has no usable geometry");
  root.position.sub(bounds.min);
  if (![origin.x, origin.z].every(Number.isFinite))
    throw Error("Scan origin must be finite");
  root.position.add(new THREE.Vector3(origin.x, 0, origin.z));
  return root;
}
