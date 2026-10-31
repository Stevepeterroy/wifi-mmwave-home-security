import { expect, test } from "vitest";
import { roomFloorGeometry, roomOutlineGeometry } from "./roomFloor";

test("concave floor preserves world coordinates and excludes the cutout", () => {
  const geometry = roomFloorGeometry({x: 2, z: 3, width: 3, depth: 3,
    boundary: [{x:2,z:3},{x:5,z:3},{x:5,z:4},{x:3,z:4},{x:3,z:6},{x:2,z:6}]});
  const positions = geometry.getAttribute("position"), indices = geometry.index!;
  let area = 0;
  for (let i = 0; i < indices.count; i += 3) {
    const a=indices.getX(i), b=indices.getX(i+1), c=indices.getX(i+2);
    area += Math.abs((positions.getX(b)-positions.getX(a))*(positions.getZ(c)-positions.getZ(a))-
      (positions.getZ(b)-positions.getZ(a))*(positions.getX(c)-positions.getX(a)))/2;
  }
  expect(area).toBeCloseTo(5);
  geometry.computeBoundingBox();
  expect(geometry.boundingBox!.min.x).toBe(2);
  expect(geometry.boundingBox!.min.z).toBe(3);
  expect(geometry.boundingBox!.max.z).toBe(6);
  expect(geometry.getAttribute("normal").getY(0)).toBeCloseTo(1);
  geometry.dispose();
});

test("room outline closes in the same scan coordinate system", () => {
  const geometry = roomOutlineGeometry({x:2,z:3,width:3,depth:2,
    boundary:[{x:2,z:3},{x:5,z:3},{x:4,z:5}]});
  const p = geometry.getAttribute("position");
  expect(p.count).toBe(4);
  expect([p.getX(0),p.getZ(0)]).toEqual([2,3]);
  expect([p.getX(2),p.getZ(2)]).toEqual([4,5]);
  expect([p.getX(3),p.getZ(3)]).toEqual([2,3]);
  geometry.dispose();
});
