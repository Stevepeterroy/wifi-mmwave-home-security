import { it, expect, vi } from "vitest";
import { scanDimensions } from "./scanDimensions";
import type { ModelAsset } from "./assets";

it("derives dimensions from GLB geometry, node transforms, model scale, axis and rotation", async () => {
  const positions = new Float32Array([0, 0, 0, 2, 0, 4, 0, 3, 4]);
  const gltf = {
    asset: { version: "2.0" },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0, translation: [10, 7, -3], scale: [2, 1, 1] }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0 } }] }],
    accessors: [
      {
        bufferView: 0,
        componentType: 5126,
        count: 3,
        type: "VEC3",
        min: [0, 0, 0],
        max: [2, 3, 4],
      },
    ],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteLength: positions.byteLength },
    ],
    buffers: [{ byteLength: positions.byteLength }],
  };
  const json = new TextEncoder().encode(JSON.stringify(gltf));
  const jsonLength = Math.ceil(json.length / 4) * 4;
  const binary = new ArrayBuffer(
    12 + 8 + jsonLength + 8 + positions.byteLength,
  );
  const view = new DataView(binary);
  view.setUint32(0, 0x46546c67, true);
  view.setUint32(4, 2, true);
  view.setUint32(8, binary.byteLength, true);
  view.setUint32(12, jsonLength, true);
  view.setUint32(16, 0x4e4f534a, true);
  new Uint8Array(binary, 20, jsonLength).fill(32);
  new Uint8Array(binary, 20, json.length).set(json);
  view.setUint32(20 + jsonLength, positions.byteLength, true);
  view.setUint32(24 + jsonLength, 0x004e4942, true);
  new Uint8Array(binary, 28 + jsonLength).set(new Uint8Array(positions.buffer));
  const model: ModelAsset = {
    id: "fixture",
    name: "fixture.glb",
    scale: 0.5,
    created: "fixture",
    files: [{ name: "fixture.glb", data: binary }],
  };
  const revoke = vi.spyOn(URL, "revokeObjectURL");
  expect(await scanDimensions(model)).toEqual({
    width: 2,
    depth: 2,
    height: 1.5,
  });
  const rotated = await scanDimensions({ ...model, upAxis: "Z", yaw: 90 });
  expect(rotated.width).toBeCloseTo(1.5);
  expect(rotated.depth).toBeCloseTo(2);
  expect(rotated.height).toBeCloseTo(2);
  expect(revoke).toHaveBeenCalledTimes(2);
  revoke.mockRestore();
});

it("rejects malformed files and preserves OBJ support", async () => {
  const model: ModelAsset = {
    id: "bad",
    name: "bad.glb",
    scale: 1,
    created: "fixture",
    files: [{ name: "bad.glb", data: new ArrayBuffer(12) }],
  };
  await expect(scanDimensions(model)).rejects.toThrow();
  const obj = new TextEncoder().encode("v 0 0 0\nv 2 0 4\nv 0 3 4\nf 1 2 3\n");
  expect(
    await scanDimensions({
      ...model,
      files: [{ name: "scan.obj", data: obj.buffer }],
    }),
  ).toEqual({ width: 2, depth: 4, height: 3 });
});
