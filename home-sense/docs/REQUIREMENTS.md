# Haven — functional requirements and delivery audit

Source of scope: goal-objective.md supplied on 9 October 2026. Home sensing is the primary app request; trial safeguards preserve the subscription reminder requirements also present in that objective. No features are considered validated merely because a screen exists.

## Current user decisions

On 10 October 2026, the user explicitly deferred phone-alert setup until later. Do not configure push keys, phone subscriptions or delivery tests now, and do not treat missing phone notifications as a blocker for current app/sensor work. Resume this setup when the user asks. HTTPS required for ESP Wi-Fi delivery remains a separate transport requirement. Google Calendar/Tasks and embedded Polycam camera integration remain excluded by earlier instructions; exported GLB import remains in scope.

## User workflow

1. Open a local workspace; enter a profile and home name.
2. Import a Polycam-exported scan, confirm model units, and align room boundaries.
3. Register a sensor, assign its room, and place its position, height, and direction on the floor plan.
4. Connect its ESP diagnostic serial port. Verify firmware and radar replies before scanning.
5. Observe fresh radar evidence on the 2D floor plan; hover or hold a room for details, and open its 3D view.
6. Enable Away mode to create motion review events, keeping replay events separate from live events.
7. Enable room care settings; display only supported, validated care measurements.
8. Add trials using receipt dates; remind on the final three days and repeat until cancellation is verified.

## Requirements audit as of 9 October 2026

1. **Antigravity as coding platform and model fallback.** Incomplete: Computer Use rejected both Antigravity apps. Model selection/exhaustion cannot be inspected. Direct development proceeds in the requested folder; no Antigravity execution is claimed.
2. **Top-down layout derived from a 3D scan.** Implemented code: Three.js orthographic mesh renderer, ceiling clipping, local GLB/GLTF/OBJ import, model units. Needs real scan and rendered verification. No scan exists in the current Desktop project inventory. Rooms require manual alignment; automatic room segmentation is not implemented.
3. **Sensor icons, module registration and position placer.** Implemented code: add-module form and clickable SVG placement map with orientation and height. Needs browser interaction verification. Independent concurrent serial readers, exclusive port ownership, per-node tracking/freshness, module-bound exports and room-bound events are implemented and tested. Simultaneous physical-node validation remains outstanding.
4. **Realtime per-room people dots/count.** Partial: genuine reflection coordinates, density groups, simple temporal association and room assignment. People count remains unavailable. A reflection cluster is not evidence of a human; no validated person classifier or multi-person count is available.
5. **Hover / phone hold room details.** Implemented handlers: hover/focus and a 450 ms touch hold reveal details; quick taps and click/keyboard Enter or Space open the spatial view. Needs pointer/touch/rendered verification.
6. **3D spatial room, movement and possible details.** Implemented code: orbit/zoom view, imported mesh or explicitly schematic geometry, reflection group trails, unavailable activity/vital fields. Real movement accuracy and scan calibration are unvalidated.
7. **Algorithms tied to project papers/slides.** Paper review completed; practical density/association baseline implemented and tested. STPM, CSI networks and fusion are not represented as running. Training/inference on labelled target-domain data is outstanding.
8. **Away-from-home alerts.** Local review-event rule implemented after three consecutive reports with moving reflections. Source and acknowledgment persisted. Remote authenticated phone delivery is outstanding; this is not a verified intrusion classifier.
9. **Elderly care: falls and stationary heartbeat/breathing.** Room care settings implemented; unsupported measurements explicitly unavailable. Requires validated fall model and supported vital-sign signal output. Current console preview is insufficient.
10. **Live ESP on specified port.** Port `/dev/cu.usbserial-11320` exists (the goal calls it usbmodem11320). Live connection attempted; fails resource busy. `lsof` identifies Arduino serial-monitor PID 13585 as owner. Computer Use also rejects Arduino control. No live data was acquired or firmware flashed this turn.
11. **First-use setup, additional modules, additional room spaces.** Profile, rooms, scan imports, module placements and saved configuration implemented. Local profile is not account authentication. Room-specific scan binding is implemented; optional password sign-in, cookie authorization and guarded TLS deployment are implemented; real browser/authenticated phone deployment remain unverified.
12. **Cross-platform phone/dashboard experience.** Responsive React app and install manifest implemented. Browser denied access to localhost:8768, so layout/touch/WebGL/PWA verification is outstanding. The server remains local-only by default. A non-loopback listener is gated on local password enrollment, TLS and explicit allowed hosts; shared authenticated scan storage is implemented and tested; actual phone deployment and model rendering remain outstanding.
13. **Trial input, high-priority buffer dates, repeated reminders and state transitions.** Forms, -3/-2/-1 date calculations, desktop reminder loop, proof/reference and verified cancellation states implemented. Calendar ICS export implemented. Google Calendar and Polycam adapters are implemented with deterministic events/retries but unconfigured and unverified against accounts. Google Tasks adapter and manual sync are implemented with marker-based reconciliation and cancellation completion, but account-level verification remains outstanding. Server Web Push scheduling, subscription controls and delivery queues are implemented; actual phone subscription and delivery remain outstanding. Neither app-open reminders nor unverified push can promise zero unintended billing.
14. **Architecture, schema and guides.** Architecture/requirements/algorithm documentation and executable sources added. End-user guide and reproducible evidence are maintained as implementation proceeds.

## Scope-preserving completion gates

- Browser approval enables UI, long-press, keyboard, 3D and mobile verification; no alternate browser or hidden headless workaround will be used for the denied action.
- Real exported home scan and geometry scale must be available to validate mapping, rooms and placements.
- Serial monitor releases specified ESP port; compatible diagnostic firmware and radar reply must be observed, then captures saved.
- Full trustworthy clouds and labelled data are required before human count, activity and fall outputs can be enabled.
- Vitals require manufacturer-supported phase/IQ or vital-sign messages; no rates inferred from point speed.
- Authenticated remote notification and calendar integration must be configured and exercised with the user's account before claimed complete.

## Verification so far

- Production React/TypeScript build passes.
- Fifteen frontend tests pass, including local scan-resource resolution, external-resource refusal and disposal of shared scan graphics resources. Domain coverage includes: transform, density grouping, temporal association/reset, room boundaries, reminder dates, cancellation state, calendar payload, independent node placement/freshness and recalibration.
- Twenty-three service tests pass, including shared-model upload, retrieval, integrity and incomplete-upload handling. Existing coverage includes: saved configuration, durable event/review merging, calendar dates and retry/cancellation behavior, missing credentials, fresh consecutive live motion, rejection of replay/duplicate/unverified frames, independent nodes, duplicate port refusal, correct module-room events, real HTTP state/export/control source binding, monitoring queue deduplication/repetition/stop/fault/version gates, password hashing/session expiry/lockout, and real HTTP cookie authorization/logout/cross-origin refusal.
- Live Away review recording runs in the server while an active scan continues; persistent scan supervision now repeats verified finite scans independently of the dashboard and stops on faults. Hardware cadence/gaps and continuous coverage remain unvalidated.
- Updated build/test dependencies have zero reported npm audit vulnerabilities.
- Backend serves production assets and data endpoints; live port failure preserved as unverified.
- Rendered UI remains unverified because Browser Use explicitly denied the request.

Room-view lifecycle fixes: changing rooms or module placement now rebuilds displayed tracks alongside the scene. Scan replacement and unmount release geometry, materials and textures, including late loads. These are code/unit-test checks; rendered WebGL behavior remains unverified.

The requested user-facing onboarding guide is in USER-GUIDE.md. It covers quick trial setup, actual reminder delivery limits, continued reminders while cancellation is pending, and provider cancellation followed by a saved confirmation reference. Scan-scale save failures surface to the user; whitespace-only cancellation references are rejected. UI interaction verification remains outstanding.

Dataset preparation: dataset.py packages new live exports with operator-provided whole-session annotations, source hashes and partial-data limits. Two dataset tests verify provenance preservation and rejection of replay, empty input and unsupported labels. No new labelled hardware capture or recognition model exists. A real HTTP test now verifies that authenticated settings saves accept an explicitly allowed remote host with a matching origin and reject mismatched origins. This does not prove phone/TLS deployment.

Phone interaction implementation: a 450 ms hold reveals room details and suppresses the resulting click; quick taps open the room, and movement over 10 pixels cancels the hold. Three gesture tests cover hold/release, quick tap and scrolling/cancellation. Keyboard focus shows details; Enter and Space open rooms. Scene is loaded dynamically so the 3D engine is deferred until a scan or spatial view is requested. Actual device behavior remains unverified under the existing browser permission denial.

Annotated-session UI and protected API are implemented. Export binds the selected module, room, placement and original host-time frames; active/pending scans, monitoring, scan faults and missing stop acknowledgments are rejected. Four dataset tests plus the existing HTTP module-binding test cover these paths. Total current checks: 15 frontend and 27 backend/dataset tests. No real labelled dataset or browser collection workflow is verified.

Google Tasks: four adapter tests cover dates/supported fields, paginated reconciliation, completion of existing generated tasks, missing credentials and refusal of ambiguous automatic insertion retries. Current total: 31 backend/dataset/integration tests and 15 frontend tests. No Google account or external task was modified.

Durable integration outcomes: pending/synced/failed records persist separately from home configuration. Two additional tests cover restart persistence and stale-attempt races; the real HTTP fixture checks Tasks outcome reporting and preservation through a home save. Current total: 33 backend/dataset/integration and 15 frontend tests. Account-level delivery and UI remain unverified.

Scan alignment now preserves a Y-up/Z-up choice and floor rotation alongside the scale. The renderer applies alignment before measuring/normalizing bounds. Three geometry tests verify conversion, rotation and empty-geometry rejection; a model-service test verifies persistence and invalid-value rejection. This does not establish alignment of an actual supplied house scan. Current tests: 18 frontend and 34 backend/dataset/integration.

Top-down overlay correction: the mesh camera now uses the same padded world rectangle and aspect fitting as the room SVG. A Three.js camera-matrix test compares projected floor coordinates with independent SVG meet-fit pixel coordinates in wide, square and narrow layouts. Current frontend tests: 19. Visual rendering with the actual home scan remains unverified.

Room extent correction: rooms extending into negative floor coordinates now remain within dashboard, sensor-placement and mesh-camera bounds. All three surfaces use shared room bounds. A geometry projection test verifies shifted bounds and negative-coordinate pixel alignment. Current frontend tests: 20. Browser placement behavior is still unverified.

Background push groundwork: optional pywebpush adapter and durable subscription/delivery queue implemented. Four fixture tests verify endpoint/key validation, restart/deduplication, service-acceptance semantics, retry/expiry and missing configuration. Subscription UI/service worker and event/scheduler wiring are still incomplete; no real push has been sent. This does not complete background notifications.

SQLite cleanup: service, authentication and test transactions now close connections on success and error. Two tests verify commit/persistence, rollback and closed-connection behavior. All 40 backend tests pass with ResourceWarning reporting enabled and no connection warnings. Background push integration and device verification remain unfinished.

Push device setup: frontend subscription controls, service worker and authenticated subscription/status/removal APIs implemented. Real HTTP fixtures cover subscription lifecycle and anonymous status denial. Actual browser registration, phone delivery and event scheduler wiring remain incomplete.

Background push scheduler and new-live-Away wiring implemented. Three scheduler tests verify durable repeat deduplication, pending cancellation, verified cancellation queue cleanup and reminder-window/removal behavior. Backend total: 43 tests. No actual subscribed phone or provider delivery has been verified; this does not establish remote alerts in operation.

Push cryptographic evidence: actual library encryption/decryption and VAPID header generation pass under a mocked transport. Deployment-key utility implemented with private files and overwrite refusal. Full backend discovery: 46 tests; real subscription/device delivery, TLS deployment and home sensing validation remain unverified.

Push delivery observability: Setup now displays configuration/enrollment prerequisites, registered workspace device count and pending/accepted/failed/expired/cancelled queue totals. Provider acceptance is explicitly not device receipt. The state API supplies only aggregate status, not endpoints or private keys. Rendered status UI remains unverified.

Notification freshness: durable message timing/expiry, legacy pending-row expiration and per-message state rechecks implemented. Away payload includes observation time. All 47 backend tests pass, including refusal to send an expired message. Real device delivery and sensing validation remain outstanding.

Live acquisition on 9 October: the user-selected native USB port `/dev/cu.usbmodem5C830803991` passed existing-firmware and radar-version checks. A finite scan produced 100 reports, 17 nonempty reports and 24 visible reflections; stop was acknowledged. GPIO21 data_bytes remained zero. Raw timestamped capture and state are retained in `data/captures/20261009T164752Z-{preview,state}.json`; summary in `docs/live-acquisition-2026-10-09.json`. No operator activity or participant annotation was supplied, so this is unlabelled observation data, not recognition validation. The registered module now uses this port. Full objective remains incomplete.

Target activity collection follow-up — 10 October 2026: Sensors now provides Save to Haven and a saved-recording review library. Immutable source readings, original unverified annotation, placement and hash persist in SQLite; reviews append history. Duplicate captures/participant-session identifiers are refused. Reviewed dataset export retains originals/reviews and excludes pending/excluded/unlabelled, short or unordered-timing sessions. Seven synthetic storage/HTTP checks pass; full backend total 62 and frontend total 24, production build passed and served. No real labelled session was acquired and the live classifier remains disabled. Evidence: evidence/activity-session-workflow-20261010.json. Actual rendered/browser collection remains unverified; phone-alert setup stays deferred.

Target training workflow — 10 October 2026: target_dataset.py and train_target.py prepare reviewed operator-annotated RD-60 previews, preserve provenance and omission/zero-report distinctions, convert cm/cm/s to m/m/s, use disjoint physical two-second windows and reject receipt/sequence gaps. Training explicitly partitions whole participants and original captures into train/validation/test; fixed 200-tree RF outputs held-out predictions and hashes without enabling live inference. Seven target checks and five source checks pass using temporary synthetic fixtures. The actual production library is empty and preparation refuses to fit/create an experiment; no real target model is claimed. Latest actual scan yielded 100 reports/50 coordinates and acknowledged stop, but GPIO21 bytes remained zero. Evidence: evidence/target-training-workflow-20261010.json and evidence/live-preview-target-check-20261010.json.

GLB placement consistency — 10 October 2026: Setup now assigns a tapped sensor using active scan rooms/geometry rather than example rectangles. An unlabeled scan gains a neutral measured Scanned space boundary; named regions replace its overlay. Placements retain scan ID and alignment, and changing scans/units/axis/rotation requires placement review. Foreign module markers, points and tracks are excluded from this plan. New modules begin unassigned until a map placement; the first-room form can prefill GLB dimensions. Exports retain room geometry, model reference and copied alignment metadata while physical calibration stays unverified. Actual 3.3283 × 4.3071 m GLB checked without modifying saved physical positions; 30 frontend, 63 backend and 12 training checks pass, build served. Evidence: evidence/glb-placement-geometry-20261010.json. Rendered browser behavior remains unverified and the broader sensing goal remains incomplete.

Room spatial coordinate follow-up: selecting an offset room no longer shifts the shared home GLB. Separate room scans use an explicit room origin, while sensors and reflection observations remain in house coordinates. Selected-room overlays exclude outside sensors/groups, 3D sensor symbols use mounting height, and trails retain consecutive in-room runs without bridging outside excursions. Missing room assets are identified before home/schematic fallback. Six new checks bring frontend total to 36; build and actual shared GLB origin/extents check pass, new assets served. No physical placement or room boundary was invented or saved during the check. Evidence: evidence/room-spatial-geometry-20261010.json. Actual browser rendering remains unverified; broader sensing/deployment requirements remain incomplete and phone-alert setup remains deferred.

11 October follow-up: imported scan surface normals are generated/repaired before applying the lit display material. Actual uploaded GLB has no NORMAL attribute; all 56,288 generated normals are finite and nonzero. Evidence: evidence/scan-lighting-20261011.json. Rendered confirmation remains pending. Saved recording coverage now identifies reviewed participant/activity/module combinations and collection gaps before offline training. All 41 frontend tests and production build pass; updated bundle served. Current ESP port remains absent and production session library empty; no target training or live deployment is claimed. Evidence: evidence/recording-coverage-20261011.json.

11 October 2026 scope change: user removed Trial safeguards. The page, navigation entry, add-trial dialog and desktop reminder loop are removed; server cancels queued trial alerts. Existing saved trial records are retained but the feature is no longer part of the requested app.
