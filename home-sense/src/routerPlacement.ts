import type { Config, RouterPlacement } from "./domain";
import type { PlacementScan } from "./planPlacement";
import { scanAlignment } from "./planPlacement";
import { homePlanBounds, type ScanFootprint } from "./planProjection";
export const routerKey = (scan?: PlacementScan) => scan ? "router:" + scan.id : "router:schematic";
export function storedRouter(config: Config, scan?: PlacementScan) {
  return config.routers?.find(r => r.id === routerKey(scan));
}
export function visibleRouter(config: Config, scan?: PlacementScan, footprint?: ScanFootprint): RouterPlacement | undefined {
  const router = storedRouter(config, scan);
  if (!router || ![router.x, router.z, router.height].every(Number.isFinite) || router.height < 0) return;
  if (scan) {
    if (!footprint || router.planModelId !== scan.id || router.scanExtent?.width !== footprint.width || router.scanExtent?.depth !== footprint.depth) return;
    const a = scanAlignment(scan), b = router.scanAlignment;
    if (!b || a.scale !== b.scale || a.upAxis !== b.upAxis || a.yaw !== b.yaw) return;
  }
  const bounds = homePlanBounds(config.rooms, footprint);
  if (router.x < bounds.minX || router.z < bounds.minZ || router.x >= bounds.minX + bounds.width || router.z >= bounds.minZ + bounds.depth) return;
  return router;
}
export function placeRouter(config: Config, point: {x: number; z: number}, scan?: PlacementScan, footprint?: ScanFootprint): Config {
  if (scan && !footprint) throw Error("Wait for the scan to finish processing before placing the router.");
  const bounds = homePlanBounds(config.rooms, footprint);
  if (![point.x, point.z].every(Number.isFinite) || point.x < bounds.minX || point.z < bounds.minZ || point.x >= bounds.minX + bounds.width || point.z >= bounds.minZ + bounds.depth) throw Error("Place the router inside this floor plan.");
  const old = storedRouter(config, scan), id = routerKey(scan);
  const keepInside = (v: number, start: number, size: number) => Math.max(start,Math.min(start + size - Math.min(1e-6,size / 2), Math.round(v * 100) / 100));
  const router: RouterPlacement = {id, name: old?.name || "Wi-Fi router", x: keepInside(point.x,bounds.minX,bounds.width), z: keepInside(point.z,bounds.minZ,bounds.depth), height: old?.height ?? 1.2, planModelId: scan?.id, scanAlignment: scan ? scanAlignment(scan) : undefined, scanExtent: scan && footprint ? {width:footprint.width,depth:footprint.depth} : undefined};
  return {...config, routers: [...(config.routers || []).filter(r => r.id !== id), router]};
}
export function updateRouter(config: Config, id: string, patch: {name?: string; height?: number}): Config {
  if (patch.height !== undefined && (!Number.isFinite(patch.height) || patch.height < 0 || patch.height > 20)) throw Error("Router mounting height must be between 0 and 20 metres.");
  if (patch.name !== undefined && (!patch.name.trim() || patch.name.length > 80)) throw Error("Use a router name containing 1–80 characters.");
  return {...config, routers: (config.routers || []).map(r => r.id === id ? {...r,...patch} : r)};
}
