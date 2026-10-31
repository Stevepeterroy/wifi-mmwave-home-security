import { useRef } from "react";
import type { Module } from "./domain";
export function radarDirection(
  m: Pick<Module, "x" | "z" | "yaw" | "fov">,
  radius = 8,
) {
  const fov = 120;
  const yaw = Number.isFinite(m.yaw) ? m.yaw : 0;
  const point = (degrees: number, distance: number) => {
    const radians = (degrees * Math.PI) / 180;
    return {
      x: m.x + Math.sin(radians) * distance,
      z: m.z + Math.cos(radians) * distance,
    };
  };
  const start = point(yaw - fov / 2, radius),
    end = point(yaw + fov / 2, radius),
    tip = point(yaw, radius);
  return {
    fov,
    tip,
    path: `M ${m.x} ${m.z} L ${start.x} ${start.z} A ${radius} ${radius} 0 0 0 ${end.x} ${end.z} Z`,
  };
}
export function facingToward(
  origin: { x: number; z: number },
  point: { x: number; z: number },
) {
  const dx = point.x - origin.x,
    dz = point.z - origin.z;
  if (!Number.isFinite(dx + dz) || Math.hypot(dx, dz) < 0.02) return null;
  return (
    Math.round((((Math.atan2(dx, dz) * 180) / Math.PI + 360) % 360) * 10) / 10
  );
}
export default function RadarDirection({
  module,
  onDirectionChange,
}: {
  module: Module;
  onDirectionChange?: (yaw: number) => void;
}) {
  const dragging = useRef<number | null>(null);
  function rotate(event: React.PointerEvent<SVGCircleElement>) {
    const svg = event.currentTarget.ownerSVGElement;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const local = point.matrixTransform(matrix.inverse());
    const yaw = facingToward(module, { x: local.x, z: local.y });
    if (yaw !== null) onDirectionChange?.(yaw);
  }
  const direction = radarDirection(module);
  const handle = onDirectionChange
    ? radarDirection(module, 0.8).tip
    : direction.tip;
  return (
    <g
      className="radar-direction"
      aria-label={`${module.name}: facing ${module.yaw} degrees, ${direction.fov} degree field of view, 8 metre nominal range`}
    >
      <path d={direction.path} className="radar-fov" />
      <path
        d={`M ${module.x} ${module.z} L ${direction.tip.x} ${direction.tip.z}`}
        className="radar-facing"
      />
      <circle
        cx={handle.x}
        cy={handle.z}
        r={onDirectionChange ? ".085" : ".035"}
        className={
          onDirectionChange ? "radar-tip radar-rotate-handle" : "radar-tip"
        }
        role={onDirectionChange ? "slider" : undefined}
        tabIndex={onDirectionChange ? 0 : undefined}
        aria-label={onDirectionChange ? `Rotate ${module.name}` : undefined}
        aria-valuemin={onDirectionChange ? 0 : undefined}
        aria-valuemax={onDirectionChange ? 360 : undefined}
        aria-valuenow={onDirectionChange ? module.yaw : undefined}
        onClick={(e) => e.stopPropagation()}
        onPointerDown={
          onDirectionChange
            ? (e) => {
                e.preventDefault();
                e.stopPropagation();
                dragging.current = e.pointerId;
                e.currentTarget.setPointerCapture(e.pointerId);
                rotate(e);
              }
            : undefined
        }
        onPointerMove={(e) => {
          if (dragging.current === e.pointerId) {
            e.preventDefault();
            e.stopPropagation();
            rotate(e);
          }
        }}
        onPointerUp={(e) => {
          if (dragging.current === e.pointerId) {
            e.stopPropagation();
            rotate(e);
            dragging.current = null;
            e.currentTarget.releasePointerCapture(e.pointerId);
          }
        }}
        onPointerCancel={() => {
          dragging.current = null;
        }}
        onLostPointerCapture={() => {
          dragging.current = null;
        }}
        onKeyDown={(e) => {
          if (
            onDirectionChange &&
            ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)
          ) {
            e.preventDefault();
            e.stopPropagation();
            const step = e.shiftKey ? 15 : 5;
            onDirectionChange(
              (module.yaw +
                (e.key === "ArrowLeft" || e.key === "ArrowDown"
                  ? -step
                  : step) +
                360) %
                360,
            );
          }
        }}
      >
        <title>
          {onDirectionChange
            ? "Drag to rotate the radar. Arrow keys rotate by 5°; Shift rotates by 15°."
            : "Radar facing direction"}
        </title>
      </circle>
    </g>
  );
}
