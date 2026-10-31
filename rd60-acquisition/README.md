# RD-60 acquisition and continuation guide

Prepared 4 October 2026 (Asia/Kolkata). This guide updates the pilot's next steps using the supplied 3 October report, the user's correction that DIP switches 4–7 were not enabled, the local datasheets, and vendor pages read on 4 October. Earlier reports remain historical records.

## 1. Main finding: first fix the data route

**On the documented RD-60-Kit V2.0.0, leaving DIP 6 OFF disconnects RD-60 PA8 (UART1 TX) from the onboard USB data adapter.** The USB adapter can still enumerate as a COM port while receiving no radar bytes. This is an evidence-backed explanation for the reported zero-byte UART1 captures; it does not prove the actual board is now fixed. The actual carrier revision and switch orientation must match the manual.

DIP 4 and 5 route flow-control signals. They are not the TX/RX data pair. DIP 6 and 7 route data TX/RX. Turning on 4/5 alone does not restore the TX route.

The carrier manual, page 13, table 3, gives:

| Switch | Radar signal | Connection enabled |
|---|---|---|
| 1 | PB0 | UART0 TX / command output |
| 2 | PB1 | UART0 RX / command input |
| 3 | NC | No functional connection |
| 4 | PA6 | UART1 RTS route |
| 5 | PA7 | UART1 CTS route |
| 6 | PA8 | RD-60 UART1 TX route |
| 7 | PA9 | RD-60 UART1 RX route |
| 8 | PA0 | RD-61 UART1 TX route |

For an **RD-60 PC bench retest**, use **1, 2, 4, 5, 6, 7 ON; 3, 8 OFF**, with ESP signal wires disconnected. This is the model-specific routing recommendation derived from the table. The vendor's shared RD-60/RD-61 quick-start instead describes all switches down in its photograph. Use the physical **ON marking** and the table, not an assumed up/down orientation. Switch 8 is the RD-61 route and is unnecessary for RD-60. The manual's English text also says “NO” where the switch label is ON.

Enabling 4/5 provides the documented handshake paths; it does **not** establish that #2967 requires PC RTS/CTS mode. Record the analyser's setting. If raw capture stays empty, test flow control as a separate controlled variable. Do not ground CTS or connect output pins together as a guess.

Sources: [carrier manual, pages 12–13 and schematic page 18](https://aithinker-static.oss-cn-shenzhen.aliyuncs.com/docs/Public%20Document%20Center/Radar/rd-6x/Specification/Rd-60-Kit_V2.0.0%20Specification-20250208.pdf), [vendor power-on guide](https://fcniufr8ibx1.feishu.cn/wiki/KzhTwGWz4ifzGpk5xcJcjSH5nqh).

## 2. Exact next bench test

1. Disconnect power from both carrier USB ports and any other supply. Disconnect ESP signal wires. Confirm the carrier revision and radar orientation. Move the DIP switches to the RD-60 PC settings above.
2. Preserve the already-working power jumpers. For USB operation, verify the carrier's VCC-3V3 I/O selection and VCC jumper against manual pages 10–12. Do not apply 5 V to VDDIO or an ESP GPIO.
3. Power normally without holding UPD. Connect both radar USB data cables to the same PC/powered hub. Identify the ports afresh by unplugging one cable; old COM3/COM4 names are not permanent.
4. First use RadarAnalysisTool with module **RD-60**, control **UART0 / 115200**, and data **UART1 / 1000000**, 8N1. The vendor power-on guide independently confirms both baud rates. Close serial monitors first; only one program should own a port.
5. Use the supplied `Rd60-PointCloudData.lua` demo or equivalent point-cloud configuration. The local demo sets 1T3R, 2DFFT, 58 GHz, 10 m range, 4 cm configured range resolution, 3 m/s maximum velocity, 37.5 cm/s configured velocity resolution, 200 ms frame period, and 10000 frames. These are settings, not measured accuracy. Stop after a short test.
6. Select the point-cloud display. Check empty scene and slow walking through the field of view. Save the analyser configuration and screenshots. A displayed cloud proves more than COM enumeration, but still does not prove complete export.
7. Stop and close the analyser. Run the raw recorder below with the finite retest command file. It captures both ports, making rejected commands and UART1 bytes available for inspection.
8. Compare the new outcome with the old zero-byte result. Keep module identity, switch settings, cables, baud rates, and flow mode in the session note.

**If still empty:** verify switch continuity with power disconnected; swap the known data cable; recheck the port assignment; inspect command responses. If available, use a 3.3 V-compatible logic analyser or oscilloscope to compare PA8 on the module side with the adapter RX path. PA8 activity but no USB bytes points toward routing/adapter/host settings. No PA8 activity points toward output configuration, handshake state, boot state, or firmware behaviour. A logic trace is needed to separate these cases. Do not reflash solely because the viewer is blank.

**If bytes arrive but display stays blank:** the physical-route problem and decode/display problem are now separate. Check RD-60 profile, point-cloud output selection, stream baud, and framing. Keep the raw capture; do not replace it with decoded guesses.

## 3. Why the UART0 text is incomplete

The [vendor shell guide](https://fcniufr8ibx1.feishu.cn/wiki/I01vwlwCeiX6qrkgfAicYjTSnqe), reached from the supplied guides, explicitly describes `mmwc data 3dpoints 4` as selecting 3D point data while printing four point details on the console. That explains the four-point preview seen in the supplied progress report.

It does not establish that `mmwc report points 100` changes this preview limit, nor that omitting the optional argument prints every point. Do not equate console lines with the complete binary stream. Query the installed firmware's `mmwc` help and verify accepted parameter ranges before experimenting with a larger console limit. Even a larger limit can overload UART0.

The guide's startup example and the prior test use different velocity settings. Keep the prior accepted configuration for the DIP retest so that routing is the main changed variable. The shell guide's numeric velocity explanation appears inconsistent with its example; it is not used here to assert measured velocity resolution.

## 4. Raw recorder: ready for the next capture

Files in this folder:

- `capture.py`: simultaneous, independent UART0/UART1 reads into binary files.
- `retest-commands.txt`: finite 100-frame configuration copied from the supplied previously accepted command sequence.
- `requirements.txt`: pySerial dependency.
- `test_capture.py`: offline preservation/error tests.

From this folder, on the computer physically attached to the radar:

```text
python -m pip install -r requirements.txt
python capture.py --list
python capture.py --control COM3 --data COM4 --seconds 25 --out captures/module2-dip-on --commands retest-commands.txt --stop-after --note "module2; RD60 kit revision verified; DIP 1,2,4,5,6,7 ON; slow walking"
```

Replace COM names with the listed devices. On macOS/Linux, use `python3` if needed and the actual serial device paths. Every output directory must be new. The recorder sends **no commands unless `--commands` is supplied**, except an explicitly requested `--stop-after`. Opening a serial port still changes host modem-control state; the tool disables DTR and asserts host RTS in non-hardware-flow mode. USB drivers may briefly change these lines while opening. Record this behaviour if reset/handshake symptoms occur.

For a separate flow-control experiment, use a new output directory and add `--data-rtscts`. Do not change baud, module, wiring and flow mode simultaneously. The default is no automatic RTS/CTS; its suitability for this firmware has not yet been verified.

Outputs include original bytes (`uart0.bin`, `uart1.bin`), per-stream chunk indices, transmitted commands, and session metadata with counts, SHA-256 hashes and exceptions. A chunk timestamp is the host's read-completion time, **not** a radar measurement timestamp. Chunk boundaries are **not** frame boundaries. Empty UART1 produces a nonzero exit status and an explicit warning. A successful byte capture does not establish zero loss: driver overruns and missing radar frames cannot be measured until the protocol is known.

Commands are paced and logged, not automatically validated against their replies. Read `uart0.bin` as text after capture and reject a session if configuration commands failed. The finite command sequence requests 100 frames at 200 ms; `--stop-after` also attempts `mmwc stop` on normal completion, interruption, or an in-session exception. A power loss or OS kill can still prevent cleanup. The next session should begin with `mmwc stop`.

The recorder is acquisition groundwork, **not an English XYZ viewer or binary decoder**. No header, checksum, point layout, or trailing field meaning has been invented. The bundled Lua demo invokes analyser APIs; it is not a packet-format specification.

## 5. RD-60 to ESP32-S3 N16R8 wiring

Keep RD-60 installed on its carrier for this pilot. N16R8 identifies 16 MB flash and 8 MB octal PSRAM in the module variant; it does not identify the development board's physical header positions. The following GPIO assignment preserves the existing pilot plan. Verify printed GPIO labels on the actual ESP board; **GPIO numbers are not header pin numbers**.

Power off both boards before wiring. Use 3.3 V logic and short wires. Power each board through its own USB input, connect signal ground, and leave ESP 3V3/5V disconnected from carrier supply pins. Keep the carrier's second USB socket empty in ESP mode. Do not modify the carrier's V13 circuit.

| RD-60-Kit J3 breakout | ESP32-S3 signal | Direction / purpose |
|---|---|---|
| Pin 1, 12, 13 or 24: GND | GND | Common reference |
| Pin 14: PB1 / radar UART0 RX | GPIO17, ESP UART1 TX | ESP sends radar commands |
| Pin 15: PB0 / radar UART0 TX | GPIO16, ESP UART1 RX | ESP receives command replies |
| Pin 23: PA8 / radar UART1 TX | GPIO18, ESP UART2 RX | ESP receives radar data |
| Pin 22: PA9 / radar UART1 RX | GPIO15, ESP UART2 TX, optional | Leave disconnected unless needed by confirmed data protocol |

**These are J3 carrier pin numbers, not bare RD-60 pin numbers.** For comparison, bare RD-60 PB1 is pin 12, PB0 pin 11, PA8 pin 22, PA9 pin 21. Match signal labels and pin-1 orientation; never copy the same numerical pin list between the two connectors. The carrier schematic was visually inspected to cross-check J3.

In ESP mode, set the carrier UART DIP bank **all OFF** to isolate onboard USB serial drivers from ESP signals. PC mode and ESP mode intentionally use different switch settings. Disconnect ESP wires before restoring PC routing. DIP OFF does not disconnect the radar from its J3 breakout; the schematic shows that breakout on the module-side nets.

Reserve GPIO19/20 for native USB when used and avoid GPIO35/36/37 on the octal-PSRAM variant. GPIO15–18 are proposed routable UART pins, not proof of availability on an unidentified board. ESP UART numbering is independent of RD-60 UART numbering.

**Important change from the old `command.ino`:** it currently uses ESP RX GPIO18 for the 115200 command UART. The proposed dual-UART wiring uses **GPIO16 for command RX** and **GPIO18 for data RX at 1000000**. Changing wires without changing that firmware will not work. The existing sketch only prints hex and does not forward PC commands.

Proposed firmware configuration, not uploaded or hardware-tested:

```text
ESP UART1: 115200, 8N1, RX GPIO16, TX GPIO17  (radar UART0 control)
ESP UART2: 1000000, 8N1, RX GPIO18           (radar UART1 data)
```

If the PC tests prove that handshake lines are required, the minimal harness is not sufficient. Carrier J3 pin 16 is PA7/CTS and pin 17 is PA6/RTS. Verify actual signal direction/polarity and the firmware's handshake use before selecting extra ESP GPIOs and configuring the driver. Do not assume matching signal names imply a valid connection.

References: local carrier manual pages 15–18; local RD-60 module manual pages 9–12; local Espressif WROOM datasheet tables 1-1 and 3-1; [Espressif UART routing and driver documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/uart.html).

## 6. STPM: feasible research candidate, not validated yet

The supplied STPM paper takes sequences of XYZ point clouds, aggregates consecutive frames, groups points with farthest-point sampling and nearest neighbours, and processes spatial/temporal representations using Mamba. RD-60's reported XYZ output matches the basic input type.

However, the report contains only short, incomplete console previews, with 0–14 reported points per frame and a nominal 5 Hz setting. The true complete-cloud density and missing-frame rate are unknown. Replicating sparse points to meet a tensor shape does not create body detail. Aggregating too much time can blur action transitions. Empty frames require explicit masks/quality handling, not fabricated points at the origin.

The paper's implementation uses 12 spatial and 10 temporal layers with hidden size 384 on a workstation with two RTX A5500 GPUs. Its benchmark accuracy is not an RD-60 result and provides no evidence that this model runs on ESP32-S3. Use the PC for decoding, training and first inference. If an exact reproduction is intended, verify author code and missing preprocessing/training details; otherwise label it an STPM-inspired adaptation.

Suggested pipeline:

```text
RD-60 UART1 bytes -> verified frame decoder -> timestamped XYZ frames
-> quality checks and labels -> fixed-duration windows -> baseline / STPM adaptation
```

Keep velocity as an optional additional feature only when its binary representation and units are verified. Keep any unidentified numeric field as unknown. Preserve raw coordinates; convert centimetres to metres only after confirming that units apply to the actual binary fields.

## 7. Continue the whole project through measured milestones

### A. Restore PC radar acquisition

Run the DIP retest. Pass evidence: nonempty UART1 capture plus corresponding command log and analyser points. This proves the data path, not complete decoding. Repeat on each module using stable labels.

### B. Establish full frames and an English viewer

Obtain vendor framing/field definitions or the analyser's documented point export. Required facts: header/synchronization, length, byte order, data type, frame ID/timestamp, point count, per-point fields/units, and checksum if present. Validate these against real captures. If documentation is absent, explicitly treat any reverse-engineered decoder as provisional until cross-checked against the analyser across empty, sparse and busy scenes.

Build a viewer only on verified decoded fields: X/Y and X/Z plots, point count, frame age, health, recording controls, and session labels. Display “sensor unavailable” on disconnect. Compare decoded point counts and geometry to the vendor display/export. Test fragmented and concatenated serial reads, bad lengths, truncated records and resynchronization.

### C. Check geometry and timing

Fix mounting orientation/height. Record marked distances and movements left/right, near/far and up/down. Establish axes and signs rather than assuming them. Record empty room, standing, sitting and walking in separate trials. Measure frame intervals, density distribution, corrupt frames and missing IDs. Acceptance targets must be set from these measured results; a 200 ms configuration alone is not timing validation.

### D. Add the ESP bridge

Only after PC capture works, implement the dual UART configuration above. Use buffered binary reads, separate control/data transport, sequence numbers, node/boot IDs and overflow/drop counters. Do not print every byte as hex at 115200: a 1 Mbaud 8N1 link can carry up to roughly 100000 bytes/s, while 115200 8N1 carries about 11520 bytes/s before hex expansion.

Start with a transport benchmark. USB native CDC or local Wi-Fi transport must sustain the measured load. Test downstream stalls and reconnects; bounded queues need explicit drops/errors rather than silent loss. Save receive times separately from RF/frame times. Proposed acceptance: 30 minutes without resets or unreported loss; report actual loss and load rather than claiming zero from byte counts alone.

### E. Bring up Wi-Fi CSI independently, then combine

Use the official [Espressif ESP-CSI repository](https://github.com/espressif/esp-csi), beginning with its router-receiver example appropriate to ESP32-S3. Pin a supported ESP-IDF/example revision and record the build. Keep router channel, bandwidth, sensor placement and traffic source recorded. Save complex CSI samples and their metadata/timestamps; RSSI alone is not CSI.

Compare empty-room and controlled-walking recordings. Then run radar and CSI concurrently with separate framed records and measured clock/arrival uncertainty. Uploading on the same radio can alter packet timing; compare isolated and combined capture performance. This is ordinary CSI, not a verified multi-antenna Wi-Fi AoA system.

### F. Collect labels and evaluate

Provisional first labels: empty, standing, sitting, walking, sit-down and stand-up. Confirm these with the project's approved application before a large collection. Record transitions separately from stationary states. Start with repeated 30–60 second feasibility trials over several sessions; this is a pilot, not a justified final training-set size. Expand participants, rooms, orientations and distances based on observed failure cases and consent.

Session manifest fields: subject ID, session/trial ID, room, module/node ID, firmware/configuration, mounting pose, activity label, label start/end times and clock basis, raw filenames, and quality notes. Capture both modalities for the same real event when evaluating fusion.

Train simple radar window features (count, centroid/spread, height and verified velocity summaries) with a small classifier. Compare against a temporal model and then STPM adaptation. Evaluate Wi-Fi only, radar only and fusion on matching held-out trials. Split by subject/session **before** overlapping windows; learn normalization on training data only. Report per-class precision/recall/F1, confusion matrix, latency, unknown/empty behaviour and nuisance detections.

### G. Final application and report

Keep sensing and application rules separate. A moving person is not inherently an intruder; an armed-zone rule needs its own evaluation. Stationary people must not disappear because a motion gate is false. Disconnects must not become empty-room predictions. Add dashboard/alerts after the sensing result is measured. Train and assess multi-person, fall or vital-sign features separately if required; they are not established by point-cloud output alone.

## 8. Evidence, limits and reference audit

- **Reported prior results:** the supplied `Copy of RD60-Project-Progress-and-Analysis-2026-10-03.md` says all three modules were flashed, two generated XYZ text, and both UART1 captures were empty. The underlying Windows logs and captures named in that report are not present in the inspected source/workspace folders, so they were not independently remeasured here.
- **User correction:** switches 4–7 were not enabled during acquisition. Combined with carrier table 3, this makes the missing PA8 route the first concrete correction.
- **Verified locally:** carrier/module pin tables and schematic; ESP module memory/pin restrictions; the actual Lua demo; the old hex-dump sketch and empty output sketch; relevant STPM method/implementation sections.
- **Verified online:** the official product page still lists #2967 as Standard Point Cloud firmware; the browser loaded all six supplied Feishu pages despite failures in the text-only web reader. Relevant sections were inspected, not every image or every child page.
- **Current hardware access:** only Bluetooth/debug serial devices were enumerated on this Mac on 4 October. No attached RD-60 port was available for a new test. No physical switch was moved, firmware uploaded, model trained or hardware fix verified.
- **Software checks:** three offline tests passed for exact binary preservation/chunk offsets, empty-stream recording, and partial-data preservation on simulated disconnect. These tests do not prove serial-driver behaviour or radar compatibility.

| Supplied reference | Identified content | Use in this solution |
|---|---|---|
| [Ai-Thinker RD-6X](https://docs.ai-thinker.com/en/rd-6x/) | Product/download index | Correct firmware family and links to manuals |
| [KLCL…](https://fcniufr8ibx1.feishu.cn/wiki/KLCLwSwxyihY80kA3dEcf0RqnXg) | Flashing guide | Carrier preparation; no repeat flashing justified |
| [X5Js…](https://fcniufr8ibx1.feishu.cn/wiki/X5JswEwlliG0A5kqe6kcqaUpnKe) | Host software index | Links to analyser, parameter configuration, data export; index is not a protocol spec |
| [KzhT…](https://fcniufr8ibx1.feishu.cn/wiki/KzhTwGWz4ifzGpk5xcJcjSH5nqh) | Power-on test | Switch routing, UART0 115200, UART1 1M, point-cloud firmware requirement |
| [Y308…](https://fcniufr8ibx1.feishu.cn/wiki/Y308wvApki39VUkOG8PcCBOXnDf) | Hardware design | Distinct power rails and GPIO supply; retain carrier supply circuitry |
| [ETkJ…](https://fcniufr8ibx1.feishu.cn/wiki/ETkJwUaFrikjOSkygoOc93ltnbf) | Radome design | Enclosure affects RF performance; validate before/after adding an enclosure |
| [ZNlU…](https://fcniufr8ibx1.feishu.cn/wiki/ZNlUw5xo6iEDq2kl733ci7hYnbh) | Introduction | RD-60/RD-61 family and shell control; not proof of finished application features |
| [Additional shell guide](https://fcniufr8ibx1.feishu.cn/wiki/I01vwlwCeiX6qrkgfAicYjTSnqe) | Command reference | Four-point console preview and startup sequence |

Immediate next action: power off, restore the RD-60 PC data routes, then perform and preserve one finite simultaneous capture. That result decides whether work proceeds to decoding or stays at electrical/output-path diagnosis.
