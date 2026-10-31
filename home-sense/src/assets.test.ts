import { describe, it, expect } from "vitest";
import { resolveLocalResource } from "./assets";
describe("scan resource boundaries", () => {
  it("resolves companion files into the supplied local blobs", () => {
    expect(
      resolveLocalResource(
        "textures/wall.png",
        new Map([["wall.png", "blob:local-texture"]]),
      ),
    ).toBe("blob:local-texture");
  });
  it("keeps embedded resources and refuses unprovided external or filesystem paths", () => {
    expect(
      resolveLocalResource(
        "data:application/octet-stream;base64,AA==",
        new Map(),
      ),
    ).toContain("data:");
    expect(resolveLocalResource("blob:local", new Map())).toBe("blob:local");
    for (const url of [
      "https://external.example/geometry.bin",
      "file:///private/home.obj",
      "javascript:alert(1)",
    ])
      expect(() => resolveLocalResource(url, new Map())).toThrow();
  });
});
