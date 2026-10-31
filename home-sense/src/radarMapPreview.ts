import {transform, withinPlan} from './domain';
import type {Frame, Module, WorldPoint} from './domain';

// A short-lived visual echo of the latest non-empty report, not a live track or person count.
export const RADAR_MAP_ECHO_SECONDS = 12;

export function recentRadarMapPoints(
  modules: Module[],
  nodes: Record<string, {connected: boolean; radar_verified: boolean; frames?: Frame[]; last_frame?: Frame | null}>,
  now: number,
  bounds: {minX: number; minZ: number; width: number; depth: number},
): {point: WorldPoint; ageSeconds: number}[] {
  return modules.flatMap((module) => {
    const node = nodes[module.id];
    if (!node?.connected || !node.radar_verified) return [];
    const reports = node.frames?.length ? node.frames : node.last_frame ? [node.last_frame] : [];
    for (const report of [...reports].reverse()) {
      if (!report.points.length || report.received_at == null || now < report.received_at ||
          now - report.received_at > RADAR_MAP_ECHO_SECONDS) continue;
      const ageSeconds = now - report.received_at;
      const visible = report.points.map((point) => ({point: transform(point, module), ageSeconds}))
        .filter(({point}) => withinPlan(point, bounds));
      if (visible.length) return visible;
    }
    return [];
  });
}
