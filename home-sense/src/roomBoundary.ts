import { ShapeUtils, Vector2 } from "three";
export type Corner = { x: number; z: number };
export type BoundaryRoom = {
  x: number;
  z: number;
  width: number;
  depth: number;
  boundary?: Corner[];
};
export function roomCorners(r: BoundaryRoom): Corner[] {
  return r.boundary?.length
    ? r.boundary
    : [
        { x: r.x, z: r.z },
        { x: r.x + r.width, z: r.z },
        { x: r.x + r.width, z: r.z + r.depth },
        { x: r.x, z: r.z + r.depth },
      ];
}
export function containsPoint(p: Corner, r: BoundaryRoom) {
  if (!r.boundary?.length)
    return (
      p.x >= r.x && p.x < r.x + r.width && p.z >= r.z && p.z < r.z + r.depth
    );
  let inside = false;
  const v = r.boundary;
  for (let i = 0, j = v.length - 1; i < v.length; j = i++) {
    const a = v[j],
      b = v[i],
      cross = (p.x - a.x) * (b.z - a.z) - (p.z - a.z) * (b.x - a.x);
    if (
      Math.abs(cross) < 1e-8 &&
      p.x >= Math.min(a.x, b.x) - 1e-8 &&
      p.x <= Math.max(a.x, b.x) + 1e-8 &&
      p.z >= Math.min(a.z, b.z) - 1e-8 &&
      p.z <= Math.max(a.z, b.z) + 1e-8
    )
      return true;
    if (
      a.z > p.z !== b.z > p.z &&
      p.x < ((b.x - a.x) * (p.z - a.z)) / (b.z - a.z) + a.x
    )
      inside = !inside;
  }
  return inside;
}
const cross = (a: Corner, b: Corner, c: Corner) =>
  (b.x - a.x) * (c.z - a.z) - (b.z - a.z) * (c.x - a.x);
function intersects(a: Corner, b: Corner, c: Corner, d: Corner) {
  const on = (p: Corner, u: Corner, v: Corner) =>
    Math.abs(cross(u, v, p)) < 1e-8 &&
    p.x >= Math.min(u.x, v.x) - 1e-8 &&
    p.x <= Math.max(u.x, v.x) + 1e-8 &&
    p.z >= Math.min(u.z, v.z) - 1e-8 &&
    p.z <= Math.max(u.z, v.z) + 1e-8;
  return (
    (cross(a, b, c) * cross(a, b, d) < 0 &&
      cross(c, d, a) * cross(c, d, b) < 0) ||
    on(c, a, b) ||
    on(d, a, b) ||
    on(a, c, d) ||
    on(b, c, d)
  );
}
export function polygonRoom(
  boundary: Corner[],
  extent: { width: number; depth: number },
) {
  if (boundary.length < 3 || boundary.length > 128)
    throw Error("Set between 3 and 128 room corners.");
  if (
    boundary.some(
      (p) =>
        !Number.isFinite(p.x + p.z) ||
        p.x < 0 ||
        p.z < 0 ||
        p.x > extent.width ||
        p.z > extent.depth,
    )
  )
    throw Error("Keep boundary points inside the scan.");
  for (let i = 0; i < boundary.length; i++) {
    const a = boundary[i],
      b = boundary[(i + 1) % boundary.length];
    if (Math.hypot(a.x - b.x, a.z - b.z) < 0.02)
      throw Error("Boundary points are too close together.");
    for (let j = i + 1; j < boundary.length; j++)
      if (
        j !== i + 1 &&
        !(i === 0 && j === boundary.length - 1) &&
        intersects(a, b, boundary[j], boundary[(j + 1) % boundary.length])
      )
        throw Error("Boundary lines cross. Undo a point and redraw.");
  }
  const area =
    Math.abs(
      boundary.reduce((s, p, i) => {
        const q = boundary[(i + 1) % boundary.length];
        return s + p.x * q.z - q.x * p.z;
      }, 0),
    ) / 2;
  if (area < 0.04) throw Error("Room boundary is too small.");
  const x = Math.min(...boundary.map((p) => p.x)),
    z = Math.min(...boundary.map((p) => p.z));
  return {
    x,
    z,
    width: Math.max(...boundary.map((p) => p.x)) - x,
    depth: Math.max(...boundary.map((p) => p.z)) - z,
    boundary: boundary.map((p) => ({ ...p })),
  };
}
function triangles(r: BoundaryRoom) {
  const p = roomCorners(r);
  return ShapeUtils.triangulateShape(
    p.map((v) => new Vector2(v.x, v.z)),
    [],
  ).map((t) => t.map((i) => p[i]));
}
function triangleOverlap(a: Corner[], b: Corner[]) {
  for (const t of [a, b])
    for (let i = 0; i < 3; i++) {
      const p = t[i],
        q = t[(i + 1) % 3],
        nx = -(q.z - p.z),
        nz = q.x - p.x;
      const aa = a.map((v) => v.x * nx + v.z * nz),
        bb = b.map((v) => v.x * nx + v.z * nz);
      if (
        Math.min(Math.max(...aa), Math.max(...bb)) -
          Math.max(Math.min(...aa), Math.min(...bb)) <=
        1e-8
      )
        return false;
    }
  return true;
}
export function roomsOverlap(a: BoundaryRoom, b: BoundaryRoom) {
  return triangles(a).some((t) =>
    triangles(b).some((u) => triangleOverlap(t, u)),
  );
}
export function roomPath(r: BoundaryRoom) {
  return (
    roomCorners(r)
      .map((p, i) => `${i ? "L" : "M"} ${p.x} ${p.z}`)
      .join(" ") + " Z"
  );
}

/** Put the room label inside its outline, including concave rooms. */
export function roomLabelPoint(room: BoundaryRoom): Corner {
  const candidates = triangles(room);
  const triangle = candidates.sort(
    (a, b) =>
      Math.abs(cross(b[0], b[1], b[2])) - Math.abs(cross(a[0], a[1], a[2])),
  )[0];
  return triangle
    ? {
        x: triangle.reduce((sum, p) => sum + p.x, 0) / 3,
        z: triangle.reduce((sum, p) => sum + p.z, 0) / 3,
      }
    : { x: room.x + room.width / 2, z: room.z + room.depth / 2 };
}
