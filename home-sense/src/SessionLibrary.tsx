import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { recordingCoverage } from "./recordingCoverage";

export const activityLabels = [
  ["unlabelled", "Unlabelled / uncertain"],
  ["empty-room", "Empty room"],
  ["walking", "Walking"],
  ["standing", "Standing"],
  ["sitting", "Sitting"],
  ["lying-down", "Lying down"],
];
type Quality = {
  reports: number;
  visible_points: number;
  reported_points: number;
  incomplete_reports: number;
  zero_point_reports: number;
  time_ordered: boolean;
  duration_seconds: number | null;
  max_gap_seconds: number | null;
  csi?: {samples:number;paired:boolean;ordered:boolean;host_overlap_seconds?:number};
};
type Review = {
  state: string;
  label: string;
  notes?: string;
  confirmed_observed?: boolean;
};
type SavedSession = {
  id: string;
  session_id: string;
  participant_id: string;
  module_id: string;
  room_id: string;
  room_assignment_verified: boolean;
  label: string;
  review_state: string;
  training_eligible: boolean;
  paired_training_candidate?: boolean;
  quality: Quality;
};
type Detail = {
  capture: unknown;
  review: Review;
  review_history: { at: string; review: Review }[];
};
type Props = {
  revision: number;
  request: (path: string, body?: unknown) => Promise<any>;
  download: (data: string, name: string) => void;
};
function Recording({
  value,
  request,
  download,
  refreshed,
}: {
  value: SavedSession;
  request: Props["request"];
  download: Props["download"];
  refreshed: () => Promise<void>;
}) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const q = value.quality;
  return (
    <details
      className="saved-recording"
      onToggle={async (e) => {
        if (!e.currentTarget.open || detail || busy) return;
        setBusy(true);
        try {
          setDetail(await request("/api/dataset/sessions/" + value.id));
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <summary>
        {value.session_id} · {value.label} · {value.review_state}
      </summary>
      <button
        type="button"
        disabled={busy}
        aria-label={`Delete recording ${value.session_id}`}
        onClick={async () => {
          if (!window.confirm(`Delete recording “${value.session_id}”? This removes its saved radar/CSI data and review history from Haven and future dataset exports. Existing exports and trained models are unchanged. This cannot be undone.`)) return;
          setBusy(true); setError("");
          try {
            await request("/api/dataset/delete", {id: value.id, confirm: true});
            await refreshed();
          } catch (e) {setError((e as Error).message);}
          finally {setBusy(false);}
        }}
      >Delete recording</button>
      <p className="muted small">
        Room: {value.room_id} {value.room_assignment_verified ? "(sensor placed here)" : "(operator-selected; sensor location unverified)"} · {value.participant_id} · {value.module_id} · {q.reports} reports ·{" "}
        {q.duration_seconds === null
          ? "Timing unavailable"
          : q.duration_seconds.toFixed(1) + " seconds"}
      </p>
      <p className="small">
        {q.visible_points} visible / {q.reported_points} reported points;{" "}
        {q.incomplete_reports} incomplete previews; {q.zero_point_reports}{" "}
        reports with zero points.
      </p>
      <p className="small">{q.csi?.samples || 0} CSI samples · {value.paired_training_candidate
        ? "CSI and radar overlap; available for paired training quality checks."
        : "No reviewed, overlapping CSI/radar pair available."}</p>
      <p className="muted small">
        {q.time_ordered
          ? "Receipt times are ordered. Largest gap: " +
            (q.max_gap_seconds?.toFixed(2) ?? "0") +
            " seconds."
          : "Receipt times are missing or out of order; this session is excluded from dataset export."}{" "}
        {value.training_eligible
          ? "Included in reviewed dataset export."
          : "Not included in reviewed dataset export. Review, a known activity and at least two seconds of ordered reports are required."}
      </p>
      {busy && <p role="status">Loading…</p>}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {detail && (
        <>
          <button
            type="button"
            onClick={() =>
              download(
                JSON.stringify(detail.capture, null, 2),
                "haven-original-session-" + value.id + ".json",
              )
            }
          >
            <Download size={16} />
            Download original recording
          </button>
          <form
            key={JSON.stringify(detail.review)}
            onSubmit={async (e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const state =
                (
                  (e.nativeEvent as SubmitEvent)
                    .submitter as HTMLButtonElement | null
                )?.value || "reviewed";
              setBusy(true);
              setError("");
              setMessage("");
              try {
                setDetail(
                  await request("/api/dataset/review", {
                    id: value.id,
                    state,
                    label: form.get("label"),
                    notes: form.get("notes"),
                    confirmObserved: form.get("confirmed") === "on",
                  }),
                );
                await refreshed();
                setMessage(
                  "Review saved. Original readings and annotation are preserved.",
                );
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Activity for this whole recording
              <select name="label" defaultValue={detail.review.label}>
                {activityLabels.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Review notes
              <textarea
                name="notes"
                maxLength={1000}
                defaultValue={detail.review.notes || ""}
                placeholder="Describe the observed activity, trial boundaries and any interruptions."
              />
            </label>
            <label className="observation-confirmation">
              <input
                type="checkbox"
                name="confirmed"
                defaultChecked={detail.review.confirmed_observed || false}
              />
              I observed this activity throughout the recording.
            </label>
            <div className="button-row">
              <button
                className="primary"
                type="submit"
                value="reviewed"
                disabled={busy}
              >
                Mark reviewed
              </button>
              <button type="submit" value="excluded" disabled={busy}>
                Exclude from dataset
              </button>
              <button type="submit" value="pending" disabled={busy}>
                Return to pending
              </button>
            </div>
          </form>
          {detail.review_history.length > 0 && (
            <details>
              <summary>Review history ({detail.review_history.length})</summary>
              {detail.review_history.map((v, i) => (
                <p key={i} className="small">
                  {v.at}: {v.review.state}, {v.review.label}. {v.review.notes}
                </p>
              ))}
            </details>
          )}
        </>
      )}
    </details>
  );
}
export default function SessionLibrary({ revision, request, download }: Props) {
  const [sessions, setSessions] = useState<SavedSession[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  async function reload() {
    setSessions(await request("/api/dataset/sessions"));
  }
  useEffect(() => {
    let active = true;
    request("/api/dataset/sessions")
      .then((values) => {
        if (active) {
          setSessions(values);
          setLoaded(true);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [revision, request]);
  const coverage = recordingCoverage(sessions);
  const eligible = coverage.eligible;
  return (
    <section className="panel">
      <h2>Saved activity recordings</h2>
      <p>
        Review what actually happened before using a recording for training.
        Labels come from your observations. Saving or reviewing a session does
        not enable activity recognition.
      </p>
      {error && <p role="alert">{error}</p>}
      {!loaded && !error && <p role="status">Loading saved recordings…</p>}
      {loaded && !sessions.length && (
        <p className="muted">
          No saved recordings yet. Finish a controlled scan above and choose
          Save to Haven.
        </p>
      )}
      {loaded && (
        <div className="saved-recording">
          <h3>Data collected for training</h3>
          <p>
            {coverage.eligible} reviewed recordings ·{" "}
            {coverage.participants.length} participants ·{" "}
            {coverage.activities.length} activities · {coverage.modules.length}{" "}
            radar modules
          </p>
          <p>{sessions.filter(s => s.paired_training_candidate).length} reviewed recordings include overlapping CSI and radar.</p>
          {coverage.participants.length < 3 && (
            <p className="muted small">
              Collect recordings from at least three distinct participants so
              training, validation and testing can use different people. Keep
              the same participant ID for each person across sessions and
              modules.
            </p>
          )}
          {coverage.activities.length < 2 && (
            <p className="muted small">
              Record and review at least two different activities to train an
              activity classifier.
            </p>
          )}
          {coverage.rows.length > 0 && (
            <ul>
              {coverage.rows.map((row) => (
                <li key={JSON.stringify([row.participant, row.module])}>
                  {row.participant} · {row.module}: {row.recordings} recordings;{" "}
                  {row.activities.length
                    ? row.activities.join(", ")
                    : "no reviewed activities"}
                  .
                  {row.missingActivities.length > 0 &&
                    ` Still missing: ${row.missingActivities.join(", ")}.`}
                </li>
              ))}
            </ul>
          )}
          <p className="muted small">
            These counts show collection coverage. They do not prove that
            recordings pass the final timing checks or that a model works on
            each radar pair. Export and run the offline training workflow to
            evaluate it; reviewed recordings alone do not enable live
            recognition.
          </p>
        </div>
      )}
      {sessions.map((value) => (
        <Recording
          key={value.id}
          value={value}
          request={request}
          download={download}
          refreshed={reload}
        />
      ))}
      <button
        disabled={!eligible || busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            download(
              JSON.stringify(
                await request("/api/dataset/training-export"),
                null,
                2,
              ),
              "haven-reviewed-dataset.json",
            );
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Download size={16} />
        Export reviewed dataset ({eligible})
      </button>
      <p className="muted small">
        The export includes original readings, placement and review history.
        Keep each participant and original recording together when splitting
        training and evaluation data. Console previews may omit points; receipt
        times are not radar acquisition times. Overlapping CSI is included when available.
      </p>
    </section>
  );
}
