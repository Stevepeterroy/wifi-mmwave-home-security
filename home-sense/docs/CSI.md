# CSI acquisition and training status

## 20 October 2026 experimental follow-up

The newly connected serial device identified itself as `RD60_CAPTURE_GPIO21 v1`,
not a CSI collector. A standalone `firmware/csi_usb` experiment is now available
for router CSI at 115200 baud, with `capture_csi_serial.py` for finite, lossless
raw captures. Compilation is verified; consult the current acquisition evidence
before assuming it has been uploaded or has received CSI. Existing Haven Wi-Fi
firmware and server addresses do not describe this standalone serial protocol.

Physical commissioning subsequently succeeded on `/dev/cu.usbmodem5C831044461`:
ESP32-S3, 16 MB flash, 8 MB PSRAM. The first 2 MiB of the prior flash were read
at 115200 and hashed before uploading; all overwritten regions lie inside that
backup. Higher-rate backup reads failed without replacing the application.
The CSI upload passed flash hash verification. The private network header is
ignored by Git. The first 30-second run contains 475 actual CSI records,
18.09 Hz over device-time intervals, RSSI −61 to −59 dBm, channel 5, zero missing
sequences and zero reported queue drops. Maximum device interval is 118 ms.
Thirteen two-second windows passed checks and the short final tail was rejected.
There are 12 always-zero IQ pair slots and no values with absolute value ≥127.
Thirteen non-JSON startup lines were inspected separately; they are not CSI.
The run is unlabelled, so no motion accuracy or occupancy claim follows.
Evidence: `data/captures/csi-usb-initial-20261020/`,
`evidence/csi-usb-initial-analysis-20261020.json`, and
`evidence/csi-firmware-backup-20261020.json`. The standalone application currently
replaces radar transport on this board; the original flash prefix is retained
at `data/captures/esp-before-csi-first2MiB-20261020.bin` for restoration.

The operator subsequently confirmed a controlled quiet/walking trial. On the
same boot, 15 quiet calibration windows passed quality gates. The existing
adjacent-packet amplitude-change rule used a quiet-derived threshold of
0.14351 and missed all nine usable walking probe windows. A candidate temporal
amplitude-variation rule instead measures RMS distance from each window's mean
normalized amplitude vector. With the same fixed threshold formula and quiet
calibration only, its threshold was 0.09647: all nine walking windows crossed
it and none of three quiet-check windows did. Because this recording informed
feature selection, it is **development evidence**, not an accuracy estimate or
independent validation. The walking probe covers 18 seconds, shorter than the
instructed 30 seconds. Phase boundaries use approximate host batch receipt time
and exclude transitions. Evidence: `evidence/csi-controlled-methods-20261020.json`.

`MotionDetector('temporal_variation')` exposes this experimental candidate;
the default remains the earlier adjacent-packet rule. No production detector
or trained activity model has been automatically switched. Both rules share
boot, channel, sequence and timing rejection and require quiet calibration.

A fresh second validation was interrupted by USB read failure after 1,082
complete raw CSI records. The old recorder did not retain per-packet host
timestamps before failure, and the walking-signal timestamp was not saved.
`data/captures/csi-usb-validation-20261020/recovered-device-only.json` preserves
the actual IQ, device milliseconds and original serial hash without inventing
host timestamps. This is not a completed validation trial. The recorder now
flushes raw bytes and timestamped decoded samples incrementally, records start
metadata immediately, and exports an explicitly incomplete capture on USB
failure or keyboard interruption. The analyzer refuses incomplete controlled
captures. Twelve relevant decoding/motion/stream/fusion tests pass, including
a simulated USB disconnection preserving a timestamped partial capture.

The subsequent 15-second reconnect check received 106 CSI records at 9.93 Hz,
RSSI −73 to −60 dBm, with a 1,060 ms maximum device-time gap and no sequence
gaps. Sequence continuity counts accepted callbacks, not all over-the-air
packets; it does not establish uninterrupted Wi-Fi reception. This degraded
link must be stabilized before validation. Evidence:
`evidence/csi-reconnect-quality-20261020.json`. The user explicitly requested
finishing analysis and deferring further physical tests. Independent validation,
multi-link experiments and target-domain activity accuracy remain unverified.

`train_csi_temporal.py` adds per-carrier robust temporal normalization,
multiscale temporal statistics and relative spectral energy. Five fixed
candidates use participants 1–4 for training and 5–6 for validation; the
validation-selected random forest scores **61.25% balanced accuracy** and
**61.91% macro F1** on participants 7–8 (560 trials). This follows an earlier
experiment on the same test participants, so it is exploratory rather than an
untouched confirmatory test. The saved model reproduces all 560 saved test
predictions. Artifacts: `data/training/csi-temporal-20261020/`; verification:
`evidence/csi-temporal-verification-20261020.json`. No source model is deployed.

ESP-Fi-HAR remains the closest inspected public ESP-based source candidate.
Its 950 × 52 amplitude inputs and approximately 98 Hz example differ from our
128-byte LLTF stream capped at 20 Hz. It also lacks an empty-room class. A high
source activity score cannot choose occupancy thresholds or establish target
fall accuracy. [WiAR](https://github.com/linteresa/WiAR) and
[Widar3.0](https://tns.thss.tsinghua.edu.cn/widar3.0/index.html) provide useful
research comparisons; their processing and sensing layouts must not be assumed
compatible with this ESP. Local labelled data remains required.

For three ESP/radar modules, start with one fixed router and three router→ESP
links placed across the areas to be monitored. This is an engineering baseline,
not a measured winner. Adding ESP↔ESP reception can provide different propagation
paths, but the existing BSSID filter rejects those packets. Cross-link experiments
must retain transmitter/receiver identity, compatible packet format, per-link
timing and drops, and use a coordinated channel and packet schedule. Joining all
devices to a router does not automatically create cross-link CSI recordings.
[Espressif describes router, inter-device and dedicated-transmitter acquisition](https://github.com/espressif/esp-csi).

Compare one router link, three router links, and router plus cross links using
the same observed activities, placements and held-out participants/days. Collect
both quiet controls and nuisance movement (fans, doors, adjacent-room movement).
Keep complete sessions in one split before windowing. Tune thresholds and fusion
on validation data only. Evaluate event recall, false alarms per quiet hour,
latency and rejected-window coverage as well as class-balanced accuracy/macro F1.
Do not treat two directions of one physical link as independent trials. Evaluate
radar-only, CSI-only and fusion on the same paired sessions. Current evidence
does not establish cross-link superiority or a fusion accuracy improvement.

For the home objectives, prioritize movement detection and radar corroboration.
Quiet CSI cannot distinguish an empty room from a stationary occupant. Room
localization/counting, falls and vital signs require separate evidence. The
motion detector now also rejects missing/duplicate sequence numbers, even when
device timestamps appear regular.

Haven now collects router LLTF CSI on the ESP32-S3 alongside radar diagnostics. The callback copies 128 signed IQ bytes, RSSI, channel, first-word-invalid flag, device milliseconds and a sequence number into a bounded queue. Sampling is limited to 20 Hz; gateway ping stimulates reception. Only packets from the connected router BSSID are accepted. CSI batches use the authenticated, certificate-verified HTTPS radar transport. Samples older than one second are discarded; dropped samples are counted. The server retains at most 2000 samples per module and exports raw readings through `/api/csi/export` with an unlabelled marker.

The Sensors page includes a 30-second quiet calibration and channel-change motion detector. It normalizes packet amplitude, discards the first four bytes, rejects timing gaps, requires 12 valid two-second baseline windows and uses a robust baseline threshold. Calibration is invalidated by a boot or channel change; recalibrate after moving the router or sensor. This is a heuristic, not a trained activity model. CSI can vary with router packet format, gain, placement and environment. Router CSI does not locate a person at the ESP icon, and it does not produce heartbeat or breathing measurements automatically.

Haven compares calibrated CSI motion with fresh radar reflection speed evidence. Both positive sources produce `corroborated_motion`; conflicts are shown as disagreements. Stale data and incomplete radar previews without moving points produce unknown evidence. This rule does not enable care alerts, infer people, or claim better accuracy. Export includes raw CSI, available radar frames and placement, with explicit timing limitations. Radar host receipt timestamps are not synchronized radar acquisition timestamps.

## Primary sources

- Espressif router CSI example and ESP32-S3 support: https://github.com/espressif/esp-csi/tree/master/examples/get-started/csi_recv_router
- ESP-Fi HAR dataset: https://github.com/AutoSmartGroup/ESP-Fi-HAR

ESP-Fi HAR provides ESP32 amplitude samples with seven activities and scenario/participant identifiers under CC BY 4.0 (per its repository documentation). Its declared format is 950 time steps × 52 subcarriers. It is a candidate for source training; collection hardware/rate/subcarrier mapping must be assessed against our raw S3 router LLTF stream before transfer. Use participant-separated evaluation and preserve the original trial identity. Do not use the test set for model selection. The provided benchmark's training/test evaluation does not substitute for target validation.

## Remaining work

The offline `train_csi_source.py` baseline validates trial identity and amplitude shape, trains on participants 1–4, selects model depth using participants 5–6 and tests once on participants 7–8. Source models are never automatically enabled on the S3 stream. Download and verify the archive, run and inspect evaluation, then collect controlled labelled target CSI sessions and paired radar–CSI recordings. Validate each branch and their synchronization before enabling trained fusion prediction. Independently collected radar and CSI datasets are not paired examples and cannot establish fused accuracy. Acquisition alone must not turn on activity, fall or vital-sign capabilities.

## Completed source experiment

The archive SHA-256 is `85f3df633c5b1a48ca4b1423467fce22821b21eeb3eed085a8d9f983dc156660`, matching the upstream Git LFS pointer. All 2240 MAT trials loaded with valid identity, finite 950 × 52 amplitude and no duplicate trial IDs. The participant-disjoint random forest baseline achieved test balanced accuracy 0.3625 and macro F1 0.36847 on 560 held-out trials. Model selection used only the separate 560 validation trials; training used 1120 trials. Artifacts are in `data/training/csi-source/`; evaluation and the trial manifest are saved separately. This performance does not justify live activity or fall deployment.

The first source raw CSV has 983 packets over 9.979333 seconds (98.40 Hz), 104 IQ bytes, signal mode 1 and channel width code 1. Our router LLTF acquisition accepts 128 IQ bytes and is bounded at 20 Hz. Direct subcarrier/timing transfer is not established. These observed differences reinforce the need for target recordings instead of resampling and assuming compatibility.

Hardware recheck: 100 radar reports, acknowledged stop, CSI 2117 received samples, zero reported queue drops, both connections verified. No human activity label was attached to this uncontrolled run. Quiet calibration and a controlled movement trial remain operator steps.

## Collect paired target recordings

1. Keep sensor/router positions fixed. Calibrate a genuinely quiet area using the Sensors button, then test a controlled movement while radar is scanning.
2. Run one finite scan per observed activity. After the acknowledged stop, enter a session identifier, a consistent pseudonymous participant ID and the activity actually observed; choose Save to Haven.
3. Save before another scan or a Haven restart. The latest completed finite scan's overlapping CSI is held separately from the rolling buffer while Haven runs. A sensor can be unassigned to a room; that unknown placement is retained explicitly instead of blocking acquisition.
4. Review the recording and confirm the whole-session observation. Interrupted or mixed trials should be excluded. The saved quality summary shows CSI/radar overlap. Overlap alone does not prove fine acquisition synchronization.
5. Collect each activity from distinct participants in each intended train, validation and test group. Export the reviewed dataset. Repeat across pairs, placements and days before evaluating generalization.

`train_paired.py` evaluates radar-only, CSI-only and concatenated feature fusion on identical two-second windows and disjoint participant groups. It rejects CSI restarts/channel changes, missing sequences, device gaps over 200 ms, zero amplitude, fewer than 24 packets, short device-time coverage and poor approximate host-time coverage. It discards the first four IQ bytes in every packet. No interpolation or fabricated samples are inserted. An observed difference between branches is reported; improvement is never assumed or automatically deployed.

Example (replace the participant IDs with those actually recorded):

```
data/training/.venv/bin/python train_paired.py \
  --bundle /absolute/path/haven-reviewed-dataset.json \
  --output data/training/new-paired-experiment \
  --train participant-A participant-B \
  --validation participant-C \
  --test participant-D
```

Outputs include original reviewed data, window provenance, modality features, three model files, predictions and results. Existing experiment folders are not overwritten. Each split must contain every evaluated activity. The current real reviewed-session library is empty; synthetic quality tests are not training evidence for the home or a radar pair.

The physical motion comparison captured 100 radar reports and 343 CSI samples, with zero CSI sequence gaps. Both motion rules were positive at two sampled checks; radar was positive while CSI stayed quiet at other checks. This supports basic channel-change motion acquisition, not validated activity recognition or an accuracy improvement claim. The capture remains unlabelled until the operator supplies and reviews the activity. The quiet baseline was explicitly requested by the user and completed; subsequent connection recovery invalidated it, as intended.

## Training/live feature parity

`live_features.py` provides dependency-free radar (50), CSI (250) and combined (300) features using the same operations and two-second window gates as offline paired training. It does not enable a model or produce activity labels. Cross-implementation tests cover varied partial/empty radar clouds, CSI invalid-word exclusion, time/sequence gaps, boot/channel changes, zero amplitude and interval validation. Seven paired/parity tests pass.

On the real unlabelled motion capture, eight windows passed quality checks and matched the offline combined features within `1e-12`; two edge windows were rejected for incomplete time coverage. Evidence is saved in `evidence/live-feature-real-capture-check.json`. This proves processing compatibility for those readings, not detection accuracy, labels, model deployment or acquisition-clock synchronization. The reviewed target library remains empty pending actual operator labels and review.

## Numeric target-model runtime

Paired training now exports `radar-rf.json`, `csi-rf.json` and `fusion-rf.json` alongside offline joblib files. `rf_runtime.py` reads numeric tree arrays without executing pickle content. It validates the target domain, feature dimensions, class labels, tree topology, finite split thresholds and leaf votes; malformed or oversized packages are refused. Tree inputs are rounded to float32 to match scikit-learn prediction semantics. Votes are model outputs, not calibrated probabilities or independent ground truth.

Cross-implementation tests compare every branch's exported package against its offline model, including values close to split thresholds. Nine runtime, feature-parity and paired-pipeline tests pass. No JSON target model is installed in the Haven service, and these test fixtures are not evidence of a trained home detector. Real reviewed target recordings, held-out evaluation and explicit model activation remain outstanding; public-source CSI models are incompatible with this target package format and are not automatically deployed.

## Explicit experimental activation

The service now includes `ActivityRuntime` and reports `activityEstimate` in `/api/state`. It is off unless a numeric target package is explicitly configured using `HAVEN_ACTIVITY_MODEL`. The runtime requires participant-disjoint training/validation/test metadata, held-out evaluation of every model class and recorded module scope. It rejects invalid packages, refuses estimates for unrecorded modules and waits when the paired window is stale, discontinuous or incomplete. Model vote fractions are not calibrated probabilities. The Sensors page labels any output as an experimental sensor-window activity estimate, not an identified person or a medical reading.

After collecting, reviewing and evaluating actual target recordings, an operator can configure a selected package when launching the service:

```
HAVEN_ACTIVITY_MODEL="/absolute/path/to/evaluated-experiment/fusion-rf.json" tools/run_home_wifi.sh
```

Review the validation/test results and branch comparisons before choosing a model. Presence of evaluation metadata alone does not make a model accurate; this activation path permits explicit experimental use and does not enable care alerts, human counts, falls, heartbeat or breathing. The current production configuration has no activity model, and the reviewed library is empty. Synthetic tests exercise model loading, paired-window inference, class/split metadata, missing data and module scope without installing a fixture in the production service.
