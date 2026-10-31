# Haven — home sensing application

React + TypeScript + Three.js dashboard with a local Python acquisition service. This app extends the earlier Radar Pilot with home/room views, placement setup, care capability status, source-labelled Away review events and trial safeguards.

## Run

Double-click `Start Haven.command`, then open http://127.0.0.1:8768. The launcher uses Haven’s separate .venv environment. Create it with a supported Python 3.11 or newer and install requirements.txt when setting up a fresh checkout. Alternatively:

```sh
npm ci
npm run build
.venv/bin/python server.py
```

For frontend development, run `npm run dev` while the Python service is running.

Read [the user guide](docs/USER-GUIDE.md) for setup, demonstration and trial-cancellation steps.

## Walkthrough

1. Enter a local profile and home name. This is a local workspace, not a cloud login.
2. Start with Replay. It uses the original 6 October ESP capture. The floor plan starts as an editable example, not a scan of your house.
3. Hover a room, or hold/tap it on a phone-sized screen, for the details. Click a room to open the 3D view and reflection trails.
4. In Setup, import a Polycam GLB, GLTF plus companion files, or OBJ. Set model units and adjust room boundaries. Imported files are stored in the workspace service and retrieved on demand by authenticated devices; browser storage provides a local cache.
5. Add a module; choose it in the placement selector and tap the map. Set mounting height and orientation. Physically calibrate the axes before treating the mapping as a location measurement.
6. Enable Away mode to test motion review events. Live review events are recorded by the service while a scan is active; the current scan is finite, so this is not continuous coverage: persistent monitoring repeats finite scans with setup gaps. Choose Start persistent monitoring in Sensors; Stop disables future cycles. Faults disable repetition. Replay events remain marked as replay. Review/export them from Activity log.
7. For live input, close other serial monitors, open Sensors, choose the ESP and connect. The app verifies existing firmware and the radar before enabling a finite scan. It never flashes firmware.
   For home Wi-Fi, Sensors now provides per-module pairing controls; see [ESP-WIFI.md](docs/ESP-WIFI.md). The prepared firmware requires private network settings and Haven's HTTPS deployment, and has not been uploaded.
8. Care settings reserve room-level monitoring; falls/vitals remain unavailable until supported and validated.
9. Add your actual trial dates in Trial safeguards. Export the three calendar reminder dates, enable desktop notifications, and enter a cancellation confirmation reference when verified. App-open notifications repeat; closing the app stops this local loop.

## Current limitations

People count, human activities, fall detection, vital signs, CSI fusion, secure remote phone alerts are unfinished. Google Calendar, Google Tasks and Polycam API adapters exist but require server credentials and account-level verification. Reflection groups are not people. Registered modules now have independent live readers, port ownership checks, freshness and tracking. Select a module in Sensors to connect or control it; other connected readers continue independently. Multi-node hardware validation remains outstanding. Room-specific scans and the active home scan selection are saved. Polycam's Content API requires Enterprise access; local exports are the available import path without that account capability.

On 9 October, live acquisition succeeded through the user-selected `/dev/cu.usbmodem5C830803991`. The radar returned firmware V4.130.4.2, 100 reports with 24 visible reflections across 17 nonempty reports, and acknowledged the final stop. GPIO21 received zero bytes, so complete binary point-cloud acquisition remains unresolved. Capture: `data/captures/20261009T164752Z-preview.json`; evidence: `docs/live-acquisition-2026-10-09.json`. These reflections have no verified human/activity labels. Browser and native-app automation permissions were denied, so rendered UI and touch/WebGL behavior remain unverified.

## Verification

`npm run build`, `npm test`, and `npm audit` pass; see docs/REQUIREMENTS.md for the scope-preserving audit. Backend API checks confirm production assets, real recorded capture totals, port enumeration and finite live acquisition with a radar stop acknowledgment. No model accuracy is claimed.

Settings/events are in `data/haven.sqlite3`; raw historical capture stays in the original project folder and is not modified. The service listens only on localhost by default; see docs/SECURE-DEPLOYMENT.md for gated authenticated TLS deployment. Do not expose it publicly without authentication and encrypted remote transport.

For new operator-annotated experiments, see [the data collection workflow](docs/DATA-COLLECTION.md). The included dataset tool retains provenance and partial-frame limits; it does not provide a trained classifier.

An initial public-dataset model has been trained on MVRHAR, with source-domain results in [TRAINING-COMPATIBILITY.md](docs/TRAINING-COMPATIBILITY.md). It is not validated on this RD-60 setup and is not used for live predictions.
