import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import type { Room, Module, Track, WorldPoint } from "./domain";
import { hydrateModel, resolveLocalResource } from "./assets";
import type { ModelAsset } from "./assets";
import { disposeObject } from "./sceneResources";
import { alignModel } from "./modelAlignment";
import { prepareScanSurface } from "./scanSurface";
import { roomFloorGeometry, roomOutlineGeometry } from "./roomFloor";
import { planFrustum, roomBounds } from "./planProjection";
import type { PlanBounds } from "./planProjection";
import { inRoom } from "./domain";
import { roomTrailSegments, sensorMarkerPosition } from "./roomScene";
export default function Scene({
  rooms,
  modules,
  tracks,
  points = [],
  model,
  plan = false,
  selected,
  planBounds,
  modelOrigin,
  focusPoints,
  pointRadius = 0.065,
}: {
  rooms: Room[];
  modules: Module[];
  tracks: Track[];
  points?: WorldPoint[];
  model?: ModelAsset;
  plan?: boolean;
  selected?: Room;
  planBounds?: PlanBounds;
  modelOrigin?: { x: number; z: number };
  focusPoints?: WorldPoint[];
  pointRadius?: number;
}) {
  const host = useRef<HTMLDivElement>(null),
    dynamic = useRef<THREE.Group | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    if (!host.current) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setError(
        "3D graphics unavailable in this browser. The 2D room layout remains available.",
      );
      return;
    }
    let disposed = false;
    setError("");
    const container = host.current;
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setClearColor("#ebece5", 1);
    container.appendChild(renderer.domElement);
    renderer.domElement.setAttribute(
      "aria-label",
      plan ? "Top view of the home model" : "Interactive 3D room",
    );
    renderer.domElement.setAttribute("role", "img");
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight("#ffffff", "#65745b", 2));
    const light = new THREE.DirectionalLight("#ffffff", 2);
    light.position.set(4, 12, 6);
    scene.add(light);
    const bounds = planBounds || roomBounds(rooms),
      maxX = bounds.width,
      maxZ = bounds.depth;
    let viewWidth = maxX, viewDepth = maxZ;
    const camera = plan
      ? new THREE.OrthographicCamera(
          -maxX / 2,
          maxX / 2,
          maxZ / 2,
          -maxZ / 2,
          0.01,
          200,
        )
      : new THREE.PerspectiveCamera(45, 1, 0.01, 200);
    const center = selected
      ? new THREE.Vector3(
          selected.x + selected.width / 2,
          0,
          selected.z + selected.depth / 2,
        )
      : new THREE.Vector3(bounds.centerX, 0, bounds.centerZ);
    const span = Math.max(selected?.width || maxX, selected?.depth || maxZ, 1);
    camera.position
      .copy(center)
      .add(
        plan
          ? new THREE.Vector3(0, 40, 0)
          : new THREE.Vector3(span * 0.9, span * 1.2, span * 1.2),
      );
    camera.up.set(0, 0, -1);
    if (!plan) camera.up.set(0, 1, 0);
    camera.lookAt(center);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(center);
    controls.enabled = !plan;
    controls.enableDamping = true;
    controls.maxPolarAngle = Math.PI / 2 - 0.04;
    const objects = new THREE.Group();
    scene.add(objects);
    const geom = new THREE.Group();
    objects.add(geom);
    function schematic() {
      for (const r of rooms) {
        const floor = new THREE.Mesh(
          roomFloorGeometry(r),
          new THREE.MeshStandardMaterial({
            color: selected?.id === r.id ? "#d8eac3" : "#d8d9cc",
          }),
        );
        floor.position.y = 0.03;
        geom.add(floor);
        if (!plan && !r.boundary?.length) {
          for (const [w, d, x, z] of [
            [r.width, 0.08, r.x + r.width / 2, r.z],
            [0.08, r.depth, r.x, r.z + r.depth / 2],
          ] as number[][]) {
            const wall = new THREE.Mesh(
              new THREE.BoxGeometry(w, 1.8, d),
              new THREE.MeshStandardMaterial({
                color: "#b7c3b3",
                transparent: true,
                opacity: 0.55,
              }),
            );
            wall.position.set(x, 0.9, z);
            geom.add(wall);
          }
        }
      }
    }
    schematic();
    if (!plan) {
      for (const room of rooms.filter(r => r.boundary?.length)) {
        const isSelected = room.id === selected?.id;
        const outline = new THREE.Line(
          roomOutlineGeometry(room),
          new THREE.LineBasicMaterial({
            color: isSelected ? "#9c7126" : "#486f60",
            depthTest: false,
            depthWrite: false,
            transparent: true,
            opacity: isSelected ? 1 : 0.55,
          }),
        );
        outline.renderOrder = 2;
        objects.add(outline);
      }
    }
    const urls: string[] = [];
    if (model) {
      hydrateModel(model)
        .then((loaded) => {
          if (disposed) return;
          const manager = new THREE.LoadingManager();
          const assets = new Map(
            loaded.files.map((f) => {
              const u = URL.createObjectURL(new Blob([f.data]));
              urls.push(u);
              return [f.name, u];
            }),
          );
          manager.setURLModifier((url) => resolveLocalResource(url, assets));
          const main = loaded.files.find((f) =>
            /\.(glb|gltf|obj)$/i.test(f.name),
          );
          if (main) {
            const done = (object: THREE.Object3D) => {
              if (disposed) {
                disposeObject(object);
                return;
              }
              object = alignModel(object, model, modelOrigin);
              if (plan && rooms.length === 0 && !selected) {
                const box = new THREE.Box3().setFromObject(object);
                for (const point of focusPoints || []) {
                  if ([point.x, point.z].every(Number.isFinite))
                    box.expandByPoint(new THREE.Vector3(point.x, 0, point.z));
                }
                const size = box.getSize(new THREE.Vector3());
                const focus = box.getCenter(new THREE.Vector3());
                focus.y = 0;
                viewWidth = Math.max(1, size.x);
                viewDepth = Math.max(1, size.z);
                camera.position.copy(focus).add(new THREE.Vector3(0, 40, 0));
                camera.lookAt(focus);
                controls.target.copy(focus);
                controls.update();
                resize();
              }
              // Event playback has no editable room layout. Frame its saved scan
              // instead of using the default 1 m camera span (an extreme close-up).
              if (!plan && rooms.length === 0 && !selected) {
                const box = new THREE.Box3().setFromObject(object);
                for (const point of focusPoints || []) {
                  if ([point.x,point.z,point.height].every(Number.isFinite))
                    box.expandByPoint(new THREE.Vector3(point.x,Math.max(0.1,point.height),point.z));
                }
                const size = box.getSize(new THREE.Vector3());
                const focus = box.getCenter(new THREE.Vector3());
                const extent = Math.max(size.x, size.y, size.z, 1);
                camera.position.copy(focus).add(new THREE.Vector3(extent * 0.9, extent * 1.2, extent * 1.2));
                camera.lookAt(focus);
                controls.target.copy(focus);
                controls.update();
              }
              disposeObject(geom);
              geom.clear();
              const originalMaterials = new Set<THREE.Material>();
              const originalTextures = new Set<THREE.Texture>();
              object.traverse((o) => {
                if (o instanceof THREE.Mesh) {
                  for (const material of Array.isArray(o.material)
                    ? o.material
                    : [o.material]) {
                    originalMaterials.add(material);
                    for (const value of Object.values(material))
                      if (value instanceof THREE.Texture)
                        originalTextures.add(value);
                  }
                  prepareScanSurface(o.geometry);
                  o.material = new THREE.MeshStandardMaterial({
                    color: "#bac5b4",
                    roughness: 0.9,
                    side: THREE.DoubleSide,
                  });
                  if (plan) {
                    (o.material as THREE.MeshStandardMaterial).clippingPlanes =
                      [new THREE.Plane(new THREE.Vector3(0, -1, 0), 1.4)];
                  }
                }
              });
              originalTextures.forEach((texture) => texture.dispose());
              originalMaterials.forEach((material) => material.dispose());
              renderer.localClippingEnabled = true;
              geom.add(object);
            };
            const fail = () => {
              if (!disposed)
                setError(
                  "Could not open this scan. Include the GLTF geometry and texture files, or export a self-contained GLB.",
                );
            };
            if (/\.obj$/i.test(main.name)) {
              try {
                done(
                  new OBJLoader(manager).parse(
                    new TextDecoder().decode(main.data),
                  ),
                );
              } catch {
                fail();
              }
            } else
              new GLTFLoader(manager).load(
                assets.get(main.name)!,
                (g) => {
                  try {
                    done(g.scene);
                  } catch {
                    disposeObject(g.scene);
                    fail();
                  }
                },
                undefined,
                fail,
              );
          }
        })
        .catch(() => {
          if (!disposed)
            setError(
              "Could not retrieve the workspace scan. Check sign-in and the local service.",
            );
        });
    }
    for (const m of modules) {
      const icon = new THREE.Mesh(
        new THREE.CylinderGeometry(0.12, 0.12, 0.12, 16),
        new THREE.MeshStandardMaterial({ color: "#284c43" }),
      );
      const position = sensorMarkerPosition(m, plan);
      icon.position.set(position.x, position.y, position.z);
      scene.add(icon);
    }
    const group = new THREE.Group();
    scene.add(group);
    dynamic.current = group;
    const resize = () => {
      const w = Math.max(1, container.clientWidth),
        h = Math.max(1, container.clientHeight);
      renderer.setSize(w, h);
      if (camera instanceof THREE.PerspectiveCamera) camera.aspect = w / h;
      else {
        Object.assign(camera, planFrustum(viewWidth, viewDepth, w, h));
      }
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();
    let raf = 0;
    const loop = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(loop);
    };
    loop();
    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      observer.disconnect();
      controls.dispose();
      disposeObject(scene);
      renderer.dispose();
      renderer.domElement.remove();
      urls.forEach((u) => URL.revokeObjectURL(u));
      dynamic.current = null;
    };
  }, [rooms, modules, model, plan, selected, planBounds, modelOrigin, focusPoints]);
  useEffect(() => {
    const group = dynamic.current;
    if (!group) return;
    disposeObject(group);
    group.clear();
    for (const p of points) {
      if (selected && !inRoom(p, selected)) continue;
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(pointRadius, 16, 16),
        new THREE.MeshBasicMaterial({ color: "#e88851", depthTest: false, depthWrite: false }),
      );
      dot.position.set(p.x, plan ? 0.2 : Math.max(0.1, p.height), p.z);
      dot.renderOrder = 20;
      group.add(dot);
    }
    for (const t of tracks) {
      if (selected && !inRoom(t, selected)) continue;
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(plan ? 0.12 : 0.1, 16, 16),
        new THREE.MeshBasicMaterial({ color: "#e88851", depthTest: false, depthWrite: false }),
      );
      dot.position.set(t.x, plan ? 0.2 : Math.max(0.1, t.height), t.z);
      dot.renderOrder = 21;
      group.add(dot);
      for (const segment of roomTrailSegments(t.trail, selected)) {
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(
            segment.map(
              (p) =>
                new THREE.Vector3(
                  p.x,
                  plan ? 0.15 : Math.max(0.1, p.height),
                  p.z,
                ),
            ),
          ),
          new THREE.LineBasicMaterial({
            color: "#c67c51",
            transparent: true,
            opacity: 0.6,
          }),
        );
        group.add(line);
      }
    }
  }, [points, tracks, rooms, modules, selected, model, plan, planBounds, modelOrigin, pointRadius]);
  return (
    <div className="scene-host" ref={host}>
      {error && <p className="scene-error">{error}</p>}
    </div>
  );
}
