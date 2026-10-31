import { lazy, Suspense, useState, useEffect } from "react";
import type { Config, Room } from "./domain";
import { uid } from "./assets";
import type { ModelAsset } from "./assets";
import type { ScanFootprint } from "./planProjection";
import { homePlanBounds, planViewBox } from "./planProjection";
import {
  partitionScan,
  savedScanRooms,
  replaceDrawnRoom,
} from "./roomPartition";
import { polygonRoom, roomPath, roomLabelPoint } from "./roomBoundary";
import type { Corner } from "./roomBoundary";
const Scene = lazy(() => import("./Scene"));
export default function RoomDrawing({
  config,
  model,
  footprint,
  onApply,
}: {
  config: Config;
  model: ModelAsset;
  footprint: ScanFootprint;
  onApply: (config: Config) => void;
}) {
  const [open, setOpen] = useState(true),
    [rooms, setRooms] = useState<Room[]>(() =>
      savedScanRooms(config, model.id),
    ),
    [editingRoom, setEditingRoom] = useState<Room | null>(null),
    [points, setPoints] = useState<Corner[]>([]),
    [pending, setPending] = useState<ReturnType<typeof polygonRoom> | null>(
      null,
    ),
    [name, setName] = useState(""),
    [error, setError] = useState("");
  useEffect(() => { setRooms(savedScanRooms(config, model.id)); }, [config.rooms, model.id]);
  function close() {
    try {
      setPending(polygonRoom(points, footprint));
      setName(editingRoom?.name || "");
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="room-drawing">
      <button
        onClick={() => {
          if (!open) {
            setError("");
          }
          setOpen(true);
          setPoints([]); setPending(null); setEditingRoom(null);
        }}
      >
        Start a new boundary
      </button>
      {open && (
        <>
          <p>
            Click or tap each corner in order around the room. Tap the first
            point again, or choose Close boundary. Then name the room and add
            it. Repeat for other sections of the house.
          </p>
          <div
            className="floor-map sensor-scan-map room-drawing-map"
            style={{ aspectRatio: `${footprint.width}/${footprint.depth}` }}
          >
            <Suspense fallback={<p>Loading scan…</p>}>
              <Scene
                rooms={[]}
                modules={[]}
                tracks={[]}
                model={model}
                plan
                planBounds={homePlanBounds([], footprint)}
              />
            </Suspense>
            <svg
              className="placement-map"
              viewBox={planViewBox(footprint.width, footprint.depth)}
              aria-label="Set room boundary points"
              onClick={(e) => {
                if (pending) return;
                const svg = e.currentTarget,
                  m = svg.getScreenCTM();
                if (!m) return;
                const p = svg.createSVGPoint();
                p.x = e.clientX;
                p.y = e.clientY;
                const q = p.matrixTransform(m.inverse());
                if (
                  q.x < 0 ||
                  q.y < 0 ||
                  q.x > footprint.width ||
                  q.y > footprint.depth
                ) {
                  setError("Choose a point inside the scan.");
                  return;
                }
                setPoints((v) => [...v, { x: q.x, z: q.y }]);
                setError("");
              }}
            >
              {rooms.map((r, index) => {
                const label = roomLabelPoint(r);
                const colour = ["#47786a", "#6175a4", "#976485", "#9b763b"][
                  index % 4
                ];
                return (
                  <g
                    key={r.id}
                    className="previous-room"
                    style={{ color: colour }}
                  >
                    <path d={roomPath(r)} className="previous-room-boundary" />
                    <text
                      x={label.x}
                      y={label.z}
                      className="previous-room-label"
                    >
                      {r.name}
                    </text>
                  </g>
                );
              })}
              {pending ? (
                <path d={roomPath(pending)} className="room-draft" />
              ) : (
                <polyline
                  points={points.map((p) => `${p.x},${p.z}`).join(" ")}
                  className="room-boundary-line"
                />
              )}
              {points.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.z}
                  r=".07"
                  className="room-corner"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (i === 0 && points.length >= 3 && !pending) close();
                  }}
                >
                  <title>
                    {i === 0
                      ? "First corner: click to close boundary"
                      : `Corner ${i + 1}`}
                  </title>
                </circle>
              ))}
            </svg>
          </div>
          {!pending ? (
            <div className="button-row">
              <button disabled={points.length < 3} onClick={close}>
                Close boundary
              </button>
              <button
                disabled={!points.length}
                onClick={() => setPoints((v) => v.slice(0, -1))}
              >
                Undo point
              </button>
              <button
                onClick={() => {
                  setPoints([]);
                  setEditingRoom(null);
                  setPending(null);
                  setError("");
                }}
              >
                {editingRoom ? "Cancel redraw" : "Clear points"}
              </button>
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                try {
                  const room: Room = {
                    ...editingRoom,
                    ...pending,
                    id: editingRoom?.id || uid(),
                    name: name.trim(),
                    care: editingRoom?.care || false,
                    modelId: model.id,
                    planModelId: model.id,
                  };
                  const next = partitionScan(
                    config,
                    model.id,
                    replaceDrawnRoom(rooms, room),
                  );
                  setRooms((v) => replaceDrawnRoom(v, room));
                  onApply(next);
                  setEditingRoom(null);
                  setPending(null);
                  setPoints([]);
                  setName("");
                  setError("");
                } catch (err) {
                  setError((err as Error).message);
                }
              }}
            >
              <label>
                Name this room
                <input
                  autoFocus
                  required
                  maxLength={80}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Living room"
                />
              </label>
              <button>Add named room</button>
              <button type="button" onClick={() => setPending(null)}>
                Edit boundary points
              </button>
            </form>
          )}
          {rooms.length > 0 && (
            <p className="muted small">
              Previously added rooms remain on the map:{" "}
              {rooms.map((r) => r.name).join(", ")}. The yellow outline is the
              room you are currently drawing.
            </p>
          )}
          {rooms.map((r) => (
            <div className="button-row" key={r.id}>
              <label>
                Room name
                <input
                  value={r.name}
                  maxLength={80}
                  onChange={(e) =>
                    setRooms((v) =>
                      v.map((q) =>
                        q.id === r.id ? { ...q, name: e.target.value } : q,
                      ),
                    )
                  }
                />
              </label>
              <button
                onClick={() => {
                  setPoints(r.boundary?.map((p) => ({ ...p })) || []);
                  setEditingRoom(r);
                  setPending(null);
                }}
              >
                Redraw boundary
              </button>
              <button
                onClick={() => {
                  onApply({ ...config, rooms: config.rooms.filter((q) => q.id !== r.id), modules: config.modules.map((m) => m.roomId === r.id ? { ...m, roomId: "" } : m) });
                  setRooms((v) => v.filter((q) => q.id !== r.id));
                  if (editingRoom?.id === r.id) { setEditingRoom(null); setPoints([]); setPending(null); }
                }}
              >
                Delete boundary
              </button>
            </div>
          ))}
          {error && <p role="alert">{error}</p>}
          <button
            disabled={
              !rooms.length || !!pending || points.length > 0 || !!editingRoom
            }
            onClick={() => {
              try {
                onApply(partitionScan(config, model.id, rooms));
                // Keep the saved collection for the next edit.
                setOpen(true);
                setError("");
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Apply named rooms
          </button>
          <p className="muted small">
            Applying replaces this scan’s existing room boundaries. Sensors keep
            their positions and are assigned using the outlined shapes. Areas
            outside the outlines remain unassigned.
          </p>
        </>
      )}
    </div>
  );
}
