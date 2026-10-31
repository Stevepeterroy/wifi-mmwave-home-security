# Standalone router CSI collector

This experimental sketch collects ESP32-S3 router LLTF CSI and emits JSON lines
at 115200 baud. It does not run the radar transport or drive radar UART pins.
Uploading it replaces the running application; retain a firmware backup or the
prior build for restoration. This is a sensing experiment, not a home alarm.

Copy `secrets.example.h` to ignored `secrets.h` and supply a 2.4 GHz network.
No laptop address, HTTPS endpoint or internet connection is required. Router
ping replies stimulate CSI; packet compatibility depends on the router.

Configure ESP32S3 Dev Module, flash 16 MB, OPI PSRAM, USB CDC disabled for the
external UART bridge used in this experiment. Compile before uploading. Identify
the actual board and port rather than relying on an old device path.

The callback accepts only the connected router BSSID and exactly 128 IQ bytes.
It copies at most 20 samples/second into a bounded queue; it never formats or
writes serial data inside the Wi-Fi callback. JSON uses 256 hexadecimal digits
to encode signed IQ bytes without exceeding the UART budget. The host restores
signed values. Do not interpret hex bytes as unsigned amplitudes. Sequence
numbers count accepted callbacks; queue losses therefore leave sequence gaps.
Status records expose total accepted samples and drops. Buffered samples older
than one second are discarded. A prolonged connection loss restarts acquisition
with a new boot identity; recalibration is required.

From the `home-sense` directory, capture a finite unlabelled trial:

```sh
.venv/bin/python capture_csi_serial.py --port /dev/cu.YOUR_PORT --baud 115200 \
  --seconds 30 --output data/captures/csi-new-trial
```

The destination must not already exist. Preserve the raw serial log, decoded
capture, summary and source hash together. Host receipt timestamps are not
acquisition timestamps. Start separate captures for observed quiet and moving
conditions; retain participant, room, placement, router, channel, day and whole
session identity. Do not retroactively label an uncontrolled capture as quiet.

For a calibrated quiet-to-movement comparison, keep **one serial connection**
open across both phases. Opening this board's serial bridge can restart the ESP;
separate captures may therefore have different boots and cannot silently share
a calibration. Record the actual instruction times and exclude transitions.
The recorder writes `start.json` and flushes timestamped `samples.jsonl` while
running. A USB failure produces `capture_complete: false` and exit code 3 while
retaining decoded data; do not count it as a completed controlled validation.

The quiet-baseline motion detector uses two-second device-time windows,
discards the first four IQ bytes, normalizes amplitude, and rejects sequence,
timing, boot and channel discontinuities. A positive score means channel change;
it does not establish presence, activity, falls, person count or vital signs.

Reference: [Espressif router CSI example](https://github.com/espressif/esp-csi/tree/master/examples/get-started/csi_recv_router).
