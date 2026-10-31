import type { Module, RouterPlacement } from "./domain";
export default function RouterOverlay({router, modules}: {router?: RouterPlacement; modules: Module[]}) {
  if (!router) return null;
  return <g className="router-overlay" pointerEvents="none" aria-label={router.name + " position"}>
    {modules.map(m => <line key={m.id} x1={router.x} y1={router.z} x2={m.x} y2={m.z} className="router-link"><title>{`${router.name} → ${m.name}: ${Math.hypot(m.x-router.x,m.z-router.z).toFixed(2)} m floor-plan distance; not measured radio coverage`}</title></line>)}
    <g transform={`translate(${router.x} ${router.z})`}>
      <path d="M0,-.22 L.22,0 0,.22 -.22,0 Z" className="router-marker"/>
      <path d="M-.11,-.025 Q0,-.13 .11,-.025 M-.065,.035 Q0,-.035 .065,.035" className="router-wave"/>
      <circle cx="0" cy=".085" r=".022" fill="#fff"/>
      <text x=".28" y="-.13" className="router-map-label">{router.name}</text>
      <title>{`${router.name}, x ${router.x.toFixed(2)} m, y ${router.z.toFixed(2)} m, height ${router.height} m`}</title>
    </g>
  </g>;
}
