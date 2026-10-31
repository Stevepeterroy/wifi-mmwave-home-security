# Haven Wi-Fi commissioning and teacher demonstration

## Current setup

The Mac runs Haven locally on http://127.0.0.1:8768. Sensor delivery uses a separate HTTPS listener on port 8769 with a private certificate explicitly trusted by the ESP32. It does not expose the workspace over plain HTTP. Use `tools/run_home_wifi.sh` to start both listeners. Keep the Mac awake and on the same network as the ESP.

The configured firmware supports router CSI and radar diagnostics independently: CSI samples are not point-cloud packets, and radar verification does not prove PA8 binary reception. The Sensors view shows CSI freshness, rate, RSSI, drop count and quiet calibration. Motion is experimental; no person count, fall or vital-sign claim is enabled.

## Change router or laptop IP

A 2.4 GHz private router may be used without internet when the Mac has a separate internet connection: the router's Ethernet remains a local route while Wi-Fi retains the default internet route. The ESP obtains authenticated clock time from Haven on UDP port 8767 before validating the HTTPS certificate on port 8769. Both ports must be reachable from the ESP. Guest/captive-portal networks and client isolation may prevent communication. Use a permitted network where the laptop and ESP can communicate.

1. Connect the laptop to the demonstration router. Find its Wi-Fi IPv4 address (`ipconfig getifaddr en0` on this Mac).
2. Stop Haven before changing its certificate.
3. From the `home-sense` directory, run:
   `.venv/bin/python tools/configure_wifi_host.py --host LAPTOP_IP --network`
   Enter the SSID and password at its local prompts. Password input is hidden. Omit `--network` when only the laptop IP changed.
4. Run `.venv/bin/python tools/check_wifi_settings.py`.
5. Rebuild and upload `firmware/rd60_wifi` using the ESP32-S3 N16R8 settings, preserving a rollback image before overwriting any new firmware. Both the endpoint and trusted certificate changed; restarting alone does not update the ESP.
6. Start `tools/run_home_wifi.sh`, restart the ESP and verify fresh CSI samples in Sensors before the demonstration.

The configuration tool backs up old private settings under ignored `data/device-tls/backup-*`; do not share those files, compiled firmware or raw flash backups. A router DHCP reservation for the laptop reduces address changes. Automatic venue discovery/provisioning and internet remote phone access are not implemented by this setup.

## Demonstration checks

- Observe increasing fresh CSI sample count; wait at least 30 seconds and check drops and timing.
- Keep the router and sensor fixed; run quiet calibration with nobody moving through the sensed link.
- Walk across the link, then return to quiet; report the actual response, not an inferred activity label.
- Moving the router/sensor or changing channel requires recalibration.
- Show radar status separately. Zero PA8 bytes remains unresolved and must not be presented as a live binary point cloud.
- USB can provide power while sensor telemetry travels via HTTPS. Unplugging USB requires a separate safe power source.

## 20 October commissioning progress

The ESP32-S3 N16R8 firmware was uploaded after preserving the first 4 MiB of its previous flash and recording its SHA-256. The device was observed in `/api/wifi/devices` as ESP32-S3 47BEFC on ROY HOME, proving that its discovery request reached Haven. The server certificate was hostname-verified for the current laptop address. The old manually paired module ID no longer matched the registered sensor, so this build uses fresh discovery enrollment instead of reusing that key.

Workspace password creation and approval of the discovered ESP remain operator steps. Until enrollment and fresh CSI delivery are observed, wireless CSI commissioning is **not complete**. No radar binary-output fix or motion accuracy claim follows from discovery.

## CSI-only commissioning update (21 October)

macOS local-network permission was corrected by the operator. A router ping that previously failed with `No route to host` then succeeded, and the ESP answered at its LAN address. This identifies a real host LAN-access blocker; it does not by itself validate CSI delivery.

`HAVEN_CSI_ONLY=1` now selects a commissioning mode that does not initialize radar GPIOs, open a radar reader or claim radar verification. Authenticated CSI packets keep the usual per-module identity, sequence, expiry and disconnect/pause rules. A mode change requires disconnect/reset. The app labels live CSI independently of radar availability. The configuration tool preserves this mode when changing routers.

## Verified wireless CSI delivery (21 October)

ESP32-S3 47BEFC was enrolled through the signed-in Sensors page into the selected `radar 1` sensor. The live card then showed fresh CSI with increasing counts (51 → 460 → 995) and zero reported device queue drops. An exported hardware capture contains 460 real 128-byte signed-IQ samples over 27.549 device seconds (16.66 Hz), one boot, channel 5, RSSI −72 to −68 dBm, maximum device interval 101 ms and zero missing accepted-callback sequence numbers. Verification and the raw export are retained in ignored `evidence/haven-wifi-commissioning-20261020/`.

The stream is authenticated, certificate-verified Wi-Fi delivery; USB was used for programming/power, not Haven acquisition. Unplugged operation requires another power source and has not been tested. This unlabelled capture verifies transport and format, not motion/occupancy accuracy. Quiet calibration remains an operator step. Radar verification is false and there are no radar frames in this capture.

## In-app Wi-Fi settings and USB flasher

Sensors → **Set up an ESP32** now contains:

1. Wi-Fi SSID, masked password, an explicit open-network choice, and the laptop LAN IPv4 address. Blank password keeps the existing secret only for the same SSID. Saving settings does not silently change the running ESP; flash afterward to apply them. Credentials stay in private ignored files and are not returned by the settings API. No passwords are written to browser local storage.
2. USB-port selection, port refresh, an explicit firmware-replacement acknowledgement, and **Back up & flash ESP32**. It uses the laptop's installed Arduino IDE/Espressif core and esptool, not Web Serial, so it is a local laptop feature—not a phone flasher. Supported configuration: ESP32-S3 N16R8, CSI-only firmware. The build is isolated and private. Compilation precedes a 4 MiB readback and SHA-256 record; no upload begins after a failed/incomplete backup. Do not disconnect USB while a job is running.

Changing the configured host rotates its private certificate and reloads the active device TLS context if that listener is running. Other devices trusting the old endpoint/certificate need reconfiguration. New devices require the existing signed-in enrollment flow after flashing. USB readers must be disconnected before flashing their port. Existing wireless sensing on the selected board is interrupted by flashing.

The local routes `/api/esp/setup` and `/api/esp/flash` require a signed-in workspace and loopback client; cross-origin writes are rejected. Device-only listeners do not serve them. Private build/backup logs are intentionally not served by the API. No flash was performed merely by adding this UI; backup/upload ordering and failure paths were exercised with fixture runners, while the real toolchain had already compiled/uploaded the same underlying CSI firmware during commissioning.

## Router position on the GLB floor plan

Setup → 03 · Sensor & Router Placement → **Place router** lets the operator tap the router’s actual location on the same metre-scale top view used for sensors. An amber diamond distinguishes it from green sensor markers. A name, mounting height, move action and remove action are provided; router positions are saved per scan without moving any sensors or changing Wi-Fi credentials. Overview also shows the reviewed router marker.

Straight dashed lines show intended router-to-ESP geometry, not measured radio coverage, wall penetration, localization or confirmed BSSID association. Placement is hidden pending review if the scan alignment, units or extent changes. Existing homes without a router position still load; no default router location is invented. Routers can be placed inside the scan footprint even where no named room exists.

## Sensor names and flash progress

Connect over home Wi-Fi now has a **Sensor display name** editor. Saving changes only the selected module's display name; its module ID, Wi-Fi pairing and floor-plan position remain unchanged. No automatic name was chosen for the operator.

The flasher now reports phase percentage parsed from the private esptool log, total elapsed time and a warning when output stops updating (45 seconds for backup/upload; 180 seconds for compilation). Raw tool output and credentials are not served. Backup verification is described as pending until the entire read finishes. No automatic retry or interruption occurs merely because output pauses. Terminal timing freezes, and the most recent finished result is retained through a service restart.

The observed job `062539ac6f644a918cbaa91cdff11578` was not stalled: the 4 MiB read took 374.4 seconds at 115200 baud, followed by a 59.7-second upload. Backup size/SHA-256 and the final written firmware hash were checked. ESP32-S3 602ABC subsequently appeared for enrollment; use a separate sensor entry for it rather than replacing the existing paired ESP.

## Combined CSI + RD-60 firmware

The flasher now offers **Wi-Fi CSI + RD-60 mmWave** and **Wi-Fi CSI only**. Combined mode requires explicit wiring confirmation: radar PB0→ESP GPIO16, PB1→GPIO17, PA8→GPIO21, common ground and isolated kit UART DIP switches OFF. Both boards need power. CSI-only mode initializes no radar GPIOs.

Combined mode forwards the existing radar command-UART diagnostics and coordinate previews through the authenticated HTTPS stream. Haven still verifies the radar version before allowing a finite scan. It also forwards bounded, unparsed UART1 byte chunks when PA8 transmits: four chunks per exchange, up to 512 bytes each, an eight-chunk device queue, expiry after one second, and the last 128 chunks retained by Haven (at most 64 KiB). Device-reported dropped-byte counts and accepted-chunk sequence gaps are separate diagnostics. Raw UART1 export is available in Sensors; it is not packet-decoded or guaranteed lossless, and no complete point-cloud claim is enabled. A physically silent PA8 remains silent despite forwarding support.

For an additional ESP, create a separate sensor entry and enroll that ESP into it. Do not replace an existing sensor’s pairing to add a second board. Existing CSI and radar captures remain source-labelled and are not acquisition-synchronized merely because they share one HTTPS envelope.

## Combined commissioning evidence

The combined build was uploaded to ESP32-S3 602ABC using job `8fff8f2e965345e8b9f1609f0f49d9ad`, after a verified 4 MiB backup. The written image hash was verified. A delayed USB command probe then received the actual `MMW version:V4.130.4.2 @1bf05415` reply, confirming the command-UART wiring. A separate unplaced sensor entry (`RD-60 + CSI · 602ABC`) was created so the existing sensor’s pairing is not replaced.

A TLS listener head-of-line-blocking issue was fixed: handshakes now run in worker threads with a deadline rather than blocking socket acceptance. A silent-peer regression test passes; the live listener again responds to hostname/certificate-verified HTTPS requests. The operator must sign in after that server restart before completing the new device enrollment. A finite hardware radar scan delivered into Haven has not yet been verified for this new combined build. Do not equate its successful upload/version reply with verified binary point-cloud delivery.
