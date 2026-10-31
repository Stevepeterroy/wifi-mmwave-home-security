/** Match SVG xMidYMid meet and the orthographic mesh camera exactly. */
export const PLAN_MARGIN = 0.3;
export type PlanBounds = ReturnType<typeof roomBounds>;
export type ScanFootprint = { width: number; depth: number; height: number };
export function homePlanBounds(
  rooms: Parameters<typeof roomBounds>[0],
  footprint?: ScanFootprint,
): PlanBounds {
  if (!footprint) return roomBounds(rooms);
  if (
    ![footprint.width, footprint.depth, footprint.height].every(
      Number.isFinite,
    ) ||
    footprint.width <= 0 ||
    footprint.depth <= 0 ||
    footprint.height < 0
  )
    throw Error("Scan has no usable floor footprint.");
  return {
    minX: 0,
    minZ: 0,
    width: footprint.width,
    depth: footprint.depth,
    centerX: footprint.width / 2,
    centerZ: footprint.depth / 2,
  };
}
export function scanRooms<
  T extends {
    x: number;
    z: number;
    width: number;
    depth: number;
    modelId?: string;
    planModelId?: string;
    scanEnvelope?: boolean;
  },
>(rooms: T[], modelId: string, bounds: PlanBounds): T[] {
  // Room labels belong to a particular scan; a new import cannot inherit demo rooms.
  const epsilon = 0.001;
  const matching = rooms.filter(
    (r) =>
      (r.planModelId === modelId ||
        (!r.planModelId && r.modelId === modelId)) &&
      r.width > 0 &&
      r.depth > 0 &&
      r.x >= bounds.minX - epsilon &&
      r.z >= bounds.minZ - epsilon &&
      r.x + r.width <= bounds.minX + bounds.width + epsilon &&
      r.z + r.depth <= bounds.minZ + bounds.depth + epsilon,
  );
  const named = matching.filter((r) => !r.scanEnvelope);
  return named.length ? named : matching;
}
export function roomBounds(
  rooms: { x: number; z: number; width: number; depth: number }[],
) {
  const minX = Math.min(0, ...rooms.map((r) => r.x)),
    minZ = Math.min(0, ...rooms.map((r) => r.z));
  const maxX = Math.max(1, ...rooms.map((r) => r.x + r.width)),
    maxZ = Math.max(1, ...rooms.map((r) => r.z + r.depth));
  return {
    minX,
    minZ,
    width: maxX - minX,
    depth: maxZ - minZ,
    centerX: (minX + maxX) / 2,
    centerZ: (minZ + maxZ) / 2,
  };
}
export function planViewBox(width: number, depth: number, minX = 0, minZ = 0) {
  return `${minX - PLAN_MARGIN} ${minZ - PLAN_MARGIN} ${width + 2 * PLAN_MARGIN} ${depth + 2 * PLAN_MARGIN}`;
}
export function planFrustum(
  width: number,
  depth: number,
  pixelWidth: number,
  pixelHeight: number,
) {
  const aspect = Math.max(1, pixelWidth) / Math.max(1, pixelHeight);
  const visibleWidth = Math.max(
    width + 2 * PLAN_MARGIN,
    (depth + 2 * PLAN_MARGIN) * aspect,
  );
  const visibleDepth = visibleWidth / aspect;
  return {
    left: -visibleWidth / 2,
    right: visibleWidth / 2,
    top: visibleDepth / 2,
    bottom: -visibleDepth / 2,
  };
}
