import { BufferGeometry, Shape, ShapeGeometry, Vector3 } from "three";
import { roomCorners, type BoundaryRoom } from "./roomBoundary";

/** World-space floor footprint; drawn boundaries do not imply physical walls. */
export function roomFloorGeometry(room: BoundaryRoom) {
  const points = roomCorners(room);
  const shape = new Shape();
  points.forEach((p, index) => {
    if (index === 0) shape.moveTo(p.x, -p.z);
    else shape.lineTo(p.x, -p.z);
  });
  shape.closePath();
  const geometry = new ShapeGeometry(shape);
  geometry.rotateX(-Math.PI / 2);
  return geometry;
}

/** A closed region outline at floor level, separate from the scanned mesh. */
export function roomOutlineGeometry(room: BoundaryRoom) {
  const points = roomCorners(room).map(p => new Vector3(p.x, 0.04, p.z));
  if (points.length) points.push(points[0].clone());
  return new BufferGeometry().setFromPoints(points);
}
