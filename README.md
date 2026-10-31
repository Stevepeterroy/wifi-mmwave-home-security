# WiFi & mmWave Home Sensing — Haven

A home sensing research prototype combining an RD-60 mmWave radar acquisition path, ESP32 Wi-Fi/CSI experiments, a local Python service, and a React/TypeScript dashboard with Three.js room views.

## Engineering highlights

- Serial radar acquisition, binary parsing and finite scan lifecycle management.
- ESP32 firmware for radar streaming, Wi-Fi pairing and CSI collection.
- Local workspace authentication, TLS configuration and device enrollment.
- Room geometry, module placement, source-labelled review events and dataset collection tools.
- React dashboard, Python backend and Capacitor Android project.

## Source layout

- `home-sense/`: main application, backend, firmware, tests and technical documentation.
- `rd60-acquisition/`: standalone capture tool and parser tests.
- `radar-demo/`: earlier radar demo and parser.

## Run locally

Use Python 3.11+ and a Node version supported by the locked Vite dependencies.

```sh
cd home-sense
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
npm run build
.venv/bin/python server.py
```

Open http://127.0.0.1:8768. Firmware setup is documented in `home-sense/docs/ESP-WIFI.md`; copy the appropriate `secrets.example.h` to ignored `secrets.h` and configure your own network, pairing credentials and trust root. Keep the service local until authentication and encrypted transport are configured.

## Validation

```sh
cd home-sense
npm test
.venv/bin/python -m unittest discover -p 'test_*.py'
```

These tests exercise software behavior; they do not establish real-world detection accuracy. See `PUBLICATION.md` for checks run on this sanitized snapshot.

## Research status and limitations

This is a prototype, not a validated security or medical device. Reflection clusters are not verified people. Falls, vital signs, people counting, activity recognition and CSI fusion must not be presented as validated capabilities. Source-dataset training does not establish accuracy on the RD-60 hardware. Multi-node and remote delivery validation remain incomplete.

Private runtime databases, captures, device certificates, trained artifacts, experiment evidence, APKs and old Git history are omitted. Some historical technical notes refer to those excluded artifacts; replay/model workflows require a new local dataset. Live acquisition requires the compatible hardware and firmware.
