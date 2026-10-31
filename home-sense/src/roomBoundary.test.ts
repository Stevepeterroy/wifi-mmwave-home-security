import { expect, it } from "vitest";
import { polygonRoom, containsPoint, roomsOverlap } from "./roomBoundary";
it("uses concave outlines rather than the bounding rectangle for membership", () => {
  const room = polygonRoom(
    [
      { x: 0, z: 0 },
      { x: 3, z: 0 },
      { x: 3, z: 1 },
      { x: 1, z: 1 },
      { x: 1, z: 3 },
      { x: 0, z: 3 },
    ],
    { width: 4, depth: 4 },
  );
  expect(containsPoint({ x: 0.5, z: 2 }, room)).toBe(true);
  expect(containsPoint({ x: 2, z: 2 }, room)).toBe(false);
  expect(roomsOverlap(room, { x: 1.5, z: 1.5, width: 1, depth: 1 })).toBe(
    false,
  );
  expect(roomsOverlap(room, { x: 0.5, z: 0.5, width: 1, depth: 1 })).toBe(true);
});
it("permits shared walls but rejects crossing boundaries and out-of-scan corners", () => {
  expect(
    roomsOverlap(
      { x: 0, z: 0, width: 1, depth: 2 },
      { x: 1, z: 0, width: 1, depth: 2 },
    ),
  ).toBe(false);
  expect(() =>
    polygonRoom(
      [
        { x: 0, z: 0 },
        { x: 2, z: 2 },
        { x: 0, z: 2 },
        { x: 2, z: 0 },
      ],
      { width: 3, depth: 3 },
    ),
  ).toThrow();
  expect(() =>
    polygonRoom(
      [
        { x: 0, z: 0 },
        { x: 4, z: 0 },
        { x: 0, z: 2 },
      ],
      { width: 3, depth: 3 },
    ),
  ).toThrow();
});

import { roomLabelPoint } from "./roomBoundary";
it("keeps labels inside previously drawn concave rooms", () => {
  const room = polygonRoom(
    [
      { x: 0, z: 0 },
      { x: 3, z: 0 },
      { x: 3, z: 1 },
      { x: 1, z: 1 },
      { x: 1, z: 3 },
      { x: 0, z: 3 },
    ],
    { width: 4, depth: 4 },
  );
  expect(containsPoint(roomLabelPoint(room), room)).toBe(true);
});
