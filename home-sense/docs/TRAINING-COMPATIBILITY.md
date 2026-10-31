# Training compatibility — 10 October 2026

The updated objective requires public-dataset research, model training and ESP Wi-Fi delivery. Google Calendar/Tasks and Polycam camera integration remain excluded by subsequent user instructions.

## Candidate datasets

MVRHAR's author repository describes TI IWR6843AOP point clouds with XYZ, Doppler and SNR, recorded at 24 frames/s. Basic labels include standing, sitting, lying and walking. Prepared clips use 24 frames and 96 points/frame. Source: https://github.com/Tianshi-Dai/MVRHAR

MiliPoint is an author-published point-cloud activity dataset and model repository. Its actual archive schema, licence and subject/session partition must be inspected before ingestion. Source: https://github.com/yizzfz/MiliPoint

## Current target input

Haven receives RD-60 console previews at a configured 5 reports/s. The console can omit points beyond its preview limit. XYZ and velocity units are centimetres and centimetres/second; the extra scalar is unlabelled and must not be called SNR. GPIO21 binary acquisition remains empty. Captures currently have no verified activity labels.

MVRHAR is a candidate for source-domain training, not proof of RD-60 compatibility. Use XYZ and Doppler only unless the RD-60 scalar is documented. Keep missing/padded points masked, preserve frame timestamps, and avoid interpreting interpolated frames as new measurements. Evaluate held-out participants and whole sessions before windowing; inspect upstream splits for overlap leakage. Record target-domain evaluation separately. No public-dataset accuracy establishes home intrusion, fall or vital-sign capability.

## Delivery requirement

Haven now has USB readers and an authenticated per-module HTTPS polling bridge, with the ESP firmware source and pairing UI. Sequence, boot identity and relative log age are retained; stale/disconnected streams fail closed. [ESP-WIFI.md](ESP-WIFI.md) records setup and verification limits. No real Wi-Fi deployment or firmware upload has been verified. Training initially runs on the laptop; ESP inference requires separate memory/latency evaluation. Do not claim that the radar firmware itself has been trained.

## Initial source-domain experiment

MVRHAR Basic was downloaded with its licence and archive hash recorded in docs/mvrhar-ingestion.json. train_baseline.py trains a seeded 200-tree Random Forest on temporal XYZ/Doppler statistics, using nonoverlapping 48-frame windows within each recording. Participant 00 is training, 01 validation and 02 testing. No SNR is used and empty frames remain empty rather than collapsing time.

The initial run completed: validation balanced accuracy 0.8023 and test balanced accuracy 0.6552. These are averages of per-class recall on MVRHAR only. The model is saved in data/training/mvrhar/source-baseline.joblib; the per-class report and confusion matrices are in source-baseline-results.json. This is a baseline rather than the requested final recognition system. The validation/test difference warrants participant-fold evaluation, source units/axes inspection, preview-sparsity and rate-shift evaluation, and RD-60 target recordings. No live classifier or ESP inference is enabled. The Wi-Fi source compiles, but no network firmware was flashed.

## Participant and sparsity study

`train_source_study.py` now trains nine models: three fixed input variants, each evaluated in three leave-one-participant-out folds. Each fold trains on the other two people. Entire recordings remain within their participant's split; two-second windows do not overlap. No hyperparameters are selected using these fold results.

The mean fold balanced accuracy is **75.51%** with native clouds, **73.92%** after 5 Hz sampling, and **69.17%** after 5 Hz sampling plus a seeded random four-point limit. For the sparse variant, individual folds range from **62.67% to 72.83%**. These scores come from MVRHAR recordings only. The comparison changes both temporal sampling and visible point information; it does not establish RD-60 accuracy.

Sampling selects the previous available source-frame time, retains missing frames and never interpolates or pads observations. XYZ/Doppler values retain original CSV units. The model uses visible point counts and ignores SNR and the extra group column. This artificial reduction does not reproduce the RD-60's point ordering, omissions, mounting position or axes. Per-view scores name the classes actually present in that view, so a missing action is not silently treated as a tested action.

Saved models, window provenance, predictions, reports and hashes are in `data/training/mvrhar/participant-sparsity-study/`. Verification reproduced every stored prediction and confusion matrix from all nine saved models, confirmed disjoint training/testing recordings and checked feature dimensions. Five isolated training checks cover timing, missing frames, point sampling, split leakage and class coverage in viewpoint metrics. Logs and proof are in `evidence/source-study-*20261010.*`.

Run with the isolated training environment:

```sh
data/training/.venv/bin/python -m unittest training_checks.source_study_test -v
data/training/.venv/bin/python train_source_study.py
```

The variability across people and the sparse-input drop reinforce the need for reviewed labelled RD-60 sessions before selecting or enabling a live activity classifier. Empty-room, multiple-person, fall and vital-sign recognition were not evaluated in the source study. Phone-alert setup remains deferred by the user.

## Target-recording experiment workflow

`target_dataset.py` and `train_target.py` now consume the reviewed dataset exported by Haven. They validate the original snapshot hash and latest operator review, reject duplicate captures and require increasing report sequences and ordered receipt times. No actual target model has been trained: the production reviewed library is empty. Running the preparer against that actual export refuses to create an experiment folder or model. Synthetic checks stay in temporary folders and are not reported as project accuracy.

Windows are disjoint two-second host-receipt intervals. Each needs at least eight observed reports, coverage within 0.4 seconds of both boundaries, no receipt gap over 0.6 seconds and no skipped report sequence inside the window. Sessions are bounded to one hour for processing. Short tails, gaps and cadence mismatches remain listed as rejected windows. No point or timestamp is interpolated or padded. These fixed exploratory thresholds describe the current configured 5 Hz preview stream; they are not certification of acquisition timing or adequate human recognition.

Coordinates and velocity convert from centimetres and centimetres/second into metres and metres/second in the radar's local axes. The 50 features include the baseline's 42 temporal XYZ/velocity/visible-count statistics plus reported-count statistics, omitted-point fraction statistics, coordinate-unavailable fraction and zero-report fraction. Thus a report with missing coordinates is distinct from a genuinely zero-point report. A zero-point report still does not prove an empty room; the activity label comes from the operator's actual observations. Module placement and firmware remain in the window provenance.

After collecting and reviewing real sessions, prepare a new experiment folder:

```sh
data/training/.venv/bin/python train_target.py --bundle haven-reviewed-dataset.json --output data/training/rd60/prepared-001
```

For a training run, explicitly assign all participant IDs to three nonempty, disjoint groups. For example, replace these placeholder IDs with the IDs actually recorded:

```sh
data/training/.venv/bin/python train_target.py --bundle haven-reviewed-dataset.json --output data/training/rd60/experiment-001 --train participant-A participant-B --validation participant-C --test participant-D
```

The training group must contain at least two activities and every activity evaluated. All windows from a participant and original capture stay in their assigned group. Use actual participant pseudonyms consistently across recordings, including associated empty-room control trials; do not invent different people to populate the splits. Plan collection across people, days, rooms and activities so each held-out group can exercise the intended classes. The report names classes missing from an evaluation split instead of implying that all classes were tested.

The fixed 200-tree Random Forest saves features, source bundle, provenance, model, held-out predictions, reports and hashes into a new private folder. Existing folders are refused. Scores are agreement with whole-session operator labels, not independently verified human recognition. Models remain offline; no score automatically enables live or ESP inference. Evaluate model error, placement changes, unseen activities, latency and count/intrusion/care behavior separately before integration. Fall/vital capabilities remain unsupported.

Seven target-pipeline checks and five source-study checks pass in the isolated training environment, including a synthetic model save/load/prediction reproduction check and refusal to fit the actual empty-library case. Evidence: `evidence/target-dataset-checks-20261010.log` and `evidence/target-empty-library-check-20261010.log`.

The latest real finite scan returned 100 reports with 50 visible coordinates matching the per-report console counts, ordered receipt times spanning 19.83 seconds, maximum gap 0.211 seconds and an acknowledged stop. GPIO21 binary bytes remained zero during this scan. Those console counts do not establish that the binary cloud is available or that any activity occurred. The new capture remains unlabelled. Evidence: `evidence/live-preview-target-check-20261010.json`.
