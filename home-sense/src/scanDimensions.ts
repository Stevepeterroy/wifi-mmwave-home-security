import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { hydrateModel, resolveLocalResource } from "./assets";
import type { ModelAsset } from "./assets";
import { alignModel } from "./modelAlignment";
import { disposeObject } from "./sceneResources";

export async function scanDimensions(model: ModelAsset) {
  const loaded = await hydrateModel(model);
  const file = loaded.files.find((f) => /\.(glb|gltf|obj)$/i.test(f.name));
  if (!file) throw Error("Scan has no supported geometry file.");
  const urls: string[] = [];
  const resources = new Map(
    loaded.files.map((f) => {
      const url = URL.createObjectURL(new Blob([f.data]));
      urls.push(url);
      return [f.name, url];
    }),
  );
  const manager = new THREE.LoadingManager();
  manager.setURLModifier((url) => resolveLocalResource(url, resources));
  let root: THREE.Object3D | undefined;
  try {
    // Layout extraction needs geometry, not image decoding or texture uploads.
    const loader = new GLTFLoader(manager);
    loader.register(() => ({
      name: "HAVEN_GEOMETRY_DIMENSIONS",
      loadTexture: async () => new THREE.Texture(),
    }));
    root = /\.obj$/i.test(file.name)
      ? new OBJLoader(manager).parse(new TextDecoder().decode(file.data))
      : (await loader.parseAsync(file.data, "")).scene;
    root = alignModel(root, model);
    const size = new THREE.Box3()
      .setFromObject(root)
      .getSize(new THREE.Vector3());
    if (size.x <= 0 || size.z <= 0)
      throw Error("Scan has no usable floor footprint.");
    return { width: size.x, depth: size.z, height: size.y };
  } finally {
    if (root) disposeObject(root);
    urls.forEach((url) => URL.revokeObjectURL(url));
  }
}
