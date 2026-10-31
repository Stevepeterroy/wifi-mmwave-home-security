# Partial sensing demo

A local demonstration built from the project's genuine ESP32-S3/RD60 captures.

## Open the demo

Run `Start Radar Demo.command`, then open http://127.0.0.1:8767.

The launcher uses the existing project Python environment. Alternatively:

```sh
python3 -m pip install -r requirements.txt
python3 server.py
```

The server listens only on this computer. Nothing is published or uploaded.

## Demonstration sequence

1. Start in **Recorded capture**. This replays the actual 6 October capture: 100 reports, 81 with detections, 459 reported reflections and 280 visible coordinate rows. Forty-seven reports have incomplete coordinate previews.
2. Pause, scrub or restart the capture. Inspect the X/Y plot and reflection counts. Hover over a point to see X/Y/Z and radial velocity.
3. Press **Arm demo rule**. Reports with reflections create local events. The UI identifies those events as recorded replay, rather than live sensing or classified intrusion.
4. Explain that the motion indicator is a rule: at least one visible reflection has absolute radial speed of 50 cm/s or more. It is not a human activity classifier.
5. Optionally connect the previously tested ESP to its COM socket, close other serial monitors, switch to **Live ESP**, select the ESP port and press **Connect ESP**. The known working port was `/dev/cu.usbmodem5C830803991`; identify it afresh when connecting.
6. Press **Start 20-second scan** only after the radar is verified. The reader uses the existing diagnostic firmware, checks `V4.130.4.2`, configures 100 reports at a nominal 200 ms period, then sends stop. The diagnostic firmware also has a 25-second stop watchdog. No firmware is flashed by this demo.

Current direct wiring: PB1/J3-14 → GPIO17, PB0/J3-15 → GPIO16, PA8/J3-23 → GPIO21, common GND, PA9 disconnected. All kit DIP switches OFF. The demo receives text previews through PB0, independently of whether the PA8 binary stream is working.

## What this proves and what it does not

- Recorded mode demonstrates a pipeline from genuine sensor output to display and a transparent application rule. It does not establish live detection today.
- Live mode can display fresh text previews and sensor status. USB enumeration alone is not treated as a verified radar connection.
- The console may show only four coordinates although the report contains more reflections. Reported count and received coordinate count remain separate.
- The recorded playback interval is the configured 200 ms; original per-report timestamps and activity labels were not recorded. No label or original timestamp is invented.
- Coordinate signs/orientation are not calibrated. The final numeric point field remains unlabelled and is not used as SNR or confidence.
- Zero points is not an empty-room prediction. Stale or disconnected data is displayed as unavailable, not negative occupancy.
- No trained STPM/activity classifier, Wi-Fi CSI acquisition, fusion, fall detection, person identification or measured model accuracy is included.

## Source data

`recorded-preview.json` is a faithful conversion of `frame-reports.csv` and `points-preview.csv` from:

`/Users/stevepeterroy/Desktop/Final Year Project Sources/rd60_esp_diagnostic/gpio21/test-20261006-203537/`

The provenance is embedded in the JSON. Original files are unchanged. JSON exports preserve the preview limitation.

## Verification

Run `python3 -m unittest test_parser.py` to check incomplete frames, signed coordinates/velocity, duplicate/orphan points and unavailable versus zero-detection reports. Recorded-mode UI and API checks are separate from live hardware validation.

Verified on 8 October 2026: three parser tests passed; all 100 report counts and 280 coordinate rows matched the original serial log. Browser checks passed for pause/scrub, recorded alert events, incomplete-preview labeling and disconnected live mode, with no browser errors. API checks confirmed the dataset totals and rejection of a scan without a verified radar. No ESP serial port was detected during this verification, so the new live reader remains untested on hardware.
