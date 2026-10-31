# Algorithm choices and evidence boundaries

## Literature reviewed

- **AI_Home_Security (2).pdf**, project slides, pp. 3–7 and 13: proposes privacy-preserving radar + CSI sensing, activity recognition, intrusion/fall applications and a STPM radar branch. These are target capabilities, not experimental evidence.
- **STPM: Spatial-Temporal Point Mamba for Activity Recognition Using mmWave Radar Point Clouds**, supplied PDF, pp. 2–6: selective bidirectional state-space processing, queue-based temporal processing and hierarchical spatial grouping. Its reported results are on RadHAR and MM-Fi. They do not transfer automatically to RD60 console snippets. The paper itself notes challenges for extremely sparse and multi-person inputs.

The complete STPM architecture is not implemented here and its benchmark accuracy is not displayed as this project's accuracy.

## Implemented baseline

1. Validate genuine coordinate rows separately from the radar's total reported count. Preserve empty and incomplete reports.
2. Convert cm → m and radial cm/s → m/s.
3. Apply module position and yaw to the radar's X/Y floor plane; use mounting height plus radar Z for the vertical coordinate. Axis orientation must be physically calibrated.
4. Run density grouping with epsilon 0.65 m and minimum two coordinate rows. Singleton reflections are noise for this grouping step. These pilot parameters are not tuned or validated human-count parameters.
5. Associate group centroids greedily within 0.9 m, using each previous track at most once. Reset after a time reversal or a gap over two seconds. Keep a bounded 15-observation trail.
6. Map world coordinates into non-overlapping room boundaries. Candidate groups may merge humans, split one human, or describe furniture/multipath; UI never relabels the group count as people.
7. Use absolute radial speed ≥0.5 m/s to describe moving reflections. No activity classifier is inferred from that single scalar.
8. In Away mode raise a source-labelled review event after three consecutive moving-reflection reports; do not claim confirmed human entry.

The current console capture exposes at most a small preview and has no activity labels. It cannot establish fall classification or heartbeat/breathing. A low radial speed does not establish a stationary person or their health.

The source-domain temporal Random Forest has now been trained and evaluated across three held-out people, including 5 Hz and four-visible-point variants. Mean fold balanced accuracy is 75.51% for native MVRHAR input and 69.17% for the reduced variant. These offline source results support a comparison baseline for the requested recognition model; they do not enable Haven's live activity, count or care capabilities. See TRAINING-COMPATIBILITY.md for experiment provenance and limits.

## Path to the requested model

- Obtain full synchronized XYZ/velocity clouds with measured cadence and loss, plus empty/stationary-person recordings.
- Collect ethically staged standing/sitting/walking/lying transitions; do not stage unsafe falls.
- Split by person/session before overlapping windows; train a simple baseline and report held-out confusion matrix, count error and false alerts.
- Evaluate adapted STPM only after suitable point sequences and training compute are available. Compare radar-only to CSI-only and fusion on matching held-out events.
- Integrate model outputs through an explicit capability/quality contract; keep unavailable values null and show source/latency.
- Add a separate vital-sign branch only if the RD60 firmware/hardware exposes a documented suitable signal. The app UI already reserves those fields without filling them with fabricated numbers.
