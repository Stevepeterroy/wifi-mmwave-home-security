# Haven workflow and model audit — 21 October 2026

Status: code, model, and live-UI audit completed; hardware sensing validation remains open.

## Initial assessment

Haven combines a Python local service, a React interface, saved 3D room layouts, ESP Wi-Fi enrollment, radar console previews, Wi-Fi CSI and an optional activity classifier. Recent changes added scan/recording deletion, grouped Away events, event previews and a Wi-Fi device inventory. These paths need integration testing, beyond their unit tests.

The running service is on localhost:8768. The workspace contains existing uncommitted changes; this audit preserves unrelated work. Past test results and earlier hardware observations are background information, not evidence for this audit.

## Verification scope

1. Workspace sign-in, expired sessions, configuration persistence and server restart recovery.
2. Scan import/deletion, room boundaries, placement/removal, map coordinate consistency and stale browser writes.
3. ESP setup, flash-job status, discovery, pairing, reconnect/revoke, connection counts and radar/CSI freshness.
4. Activity recording, review, deletion, exports, actual available model artifacts, feature compatibility and live inference gates.
5. Away-event start/continuation/cooldown, loss of signal, multiple sensors, event capture, individual export and 3D playback.
6. UI navigation, error recovery, confirmations, responsive layout, labels and accessible controls.
7. Security boundaries relevant to the workflow: credentials, authenticated writes, device-only transport and file IDs.

## Evidence and completion criteria

Run the full Python and frontend suites and production build, then add regression checks for confirmed defects. Exercise the rendered UI with the running service, using an isolated fixture service when destructive flows or signed-in workflows need test data. Inspect actual configured models and report their training/evaluation scope. Record which hardware paths can be tested with devices presently available.

Completion requires verified fixes for confirmed defects, a final evidence summary, and explicit separation of tested behavior from unavailable hardware/model accuracy validation. No real recordings, layouts, pairing credentials or firmware will be replaced merely to run synthetic tests.

## Findings and fixes

### Flash recovery — fixed

The stalled ESP32-S3 job had completed a 4 MiB backup but had not uploaded the desired firmware. Its owner process had died, leaving the UI on “Backing up” for over an hour. The USB board MAC matched the backup log; a fresh read of static flash regions matched the backup. The backup was SHA-256 recorded, the compiled firmware was uploaded at 115200 baud, and esptool reported **“Hash of data verified.”** The job now persists as `Firmware installed`, with a verified backup. No second flash is needed. This proves the upload to the connected USB board, **not** RD-60 UART1 point delivery or Wi-Fi enrollment. The board MAC differs from the sensor's old display-name suffix; do not infer a pairing from the name.

The job reconciler now distinguishes a completed backup with no upload from a verified upload after an owner crash, instead of reporting the same ambiguous state. The flasher UI polls while running so external recovery does not leave a stale status. A regression test covers the interrupted-job case.

### Service security — fixed

The local HTTP service previously accepted arbitrary Host and Origin values merely ending in `:8768`. It now permits exact loopback hosts or explicitly configured hosts and requires the Origin to match the request's scheme and Host. Cross-site and malformed Host/Origin regressions are tested. This reduces cross-origin and host-header confusion without widening local-network access.

### UI and workflow — fixed/verified

Read-only live UI checks covered Overview, Sensors, Activity log, Setup and Care at the current browser viewport. The active scan and room overlays rendered, while the connected-device count correctly remained zero. The recovered flash state appeared after refreshing ports. Empty Activity log had an enabled “Delete all events” button; it is now disabled when there are no events. Care-room buttons implied active care monitoring even though the implementation only saved a future-use marker; they now explicitly say “Mark for future care.” No live fall, heartbeat or breathing claim is made.

### Models — not live-validated

The available CSI temporal artifact is a **source-domain** ESP-Fi-HAR model (3,328 features, seven activity classes). Its source held-out participant balanced accuracy is 0.6125, macro F1 0.6191. The older 728-feature source model scores 0.3625 balanced accuracy. Their metadata explicitly sets `live_enabled=false` and `target_validated=false`. `HAVEN_ACTIVITY_MODEL` is not configured. No participant-disjoint evaluation on the current RD-60/ESP pair exists in this workspace, so Haven must not present these as trained live-home activity, fall, or vital-sign models. The saved-library database currently has two activity sessions, one reviewed; an older RD-60 training export contains zero sessions and is not evidence of current target validation.

### Tests and limits

- Initial baseline: 125 Python tests, 67 frontend tests, production build passed.
- Final after fixes: **126 Python tests**, **67 frontend tests**, and production build passed. Logs are in this directory. The only build warning is a 575 kB JavaScript chunk.
- Physical radar UART1 output and continuous point-cloud/CSI Wi-Fi delivery were not established by these software tests. No oscilloscope/logic analyzer measurement was available. The user must keep the radar and ESP powered and verify packet delivery, pairing, and calibration before relying on live sensing.
- The live service had no connected ESP and no verified radar during UI inspection. No real recordings, scans, pairings or events were deleted for this audit.

## Remaining recommendations

1. Instrument PA8/UART1 and verify binary bytes at the configured baud rate, then repeat with ESP GPIO21 while checking common ground.
2. Run an end-to-end Wi-Fi enrollment and finite radar/CSI capture on the actual sensor pair; confirm freshness and frame counts before enabling monitoring.
3. Collect and review multiple participants and activities in this space, then perform a participant-disjoint target evaluation before any live model or fall-detection claims.
4. Consider code-splitting the frontend bundle; this is a performance warning, not a failed build.
