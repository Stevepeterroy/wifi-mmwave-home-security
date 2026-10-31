# ESP-to-Haven Wi-Fi connection

The ESP can deliver the existing RD-60 diagnostic stream to Haven over authenticated HTTPS. Each sensor has its own pairing key, connection, radar verification and scan controls. This sends console previews; it does not recover the missing PA8 binary point cloud or enable human classification, falls or vital signs.

The source and service are implemented and tested. The ESP firmware compiles for the installed ESP32-S3 core, but has **not been uploaded or tested over real Wi-Fi**. Production Wi-Fi credentials, workspace enrollment and a reachable HTTPS deployment remain required.

## Prepare Haven

1. Open Haven locally and choose Sensors → Set up sign-in for Wi-Fi pairing to create your own workspace password. No preset password is provided.
2. Configure a trusted HTTPS hostname and listener using [SECURE-DEPLOYMENT.md](SECURE-DEPLOYMENT.md). Keep the laptop/server running. For access beyond home Wi-Fi, the hostname must also reach that server over the internet; localhost cannot do this. Remote reachability is not configured here.
3. In Sensors, select the intended registered sensor and disconnect its current USB reader. Wait for the status to show disconnected.
4. Select **Create Wi-Fi pairing key**. Copy the key and the sensor ID into that ESP's private settings. The key is returned once; creating another replaces the old one. It cannot sign into the workspace or control other sensors.

## Prepare each ESP

Copy `firmware/rd60_wifi/secrets.example.h` to `secrets.h` in the same directory. This private file is ignored by Git. Fill in:

- `HAVEN_WIFI_SSID` and `HAVEN_WIFI_PASSWORD`: the home network.
- `HAVEN_MODULE_ID`: the exact ID shown for this sensor in Haven.
- `HAVEN_DEVICE_TOKEN`: its pairing key.
- `HAVEN_EXCHANGE_URL`: the full HTTPS URL ending in `/api/wifi/exchange`.
- `HAVEN_ROOT_CA`: the PEM root certificate that validates that hostname. Use a C++ raw string literal for a multiline PEM. Certificate validation is required; do not use `setInsecure()`.

Before building, run `python3 tools/check_wifi_settings.py` from the project directory. This read-only check reports missing settings, localhost/example URLs, invalid endpoint paths and unparseable CA certificates without printing private values. A passing result does not verify Wi-Fi reachability, certificate hostname or device authorization.

Build `rd60_wifi.ino` for ESP32S3 Dev Module, USB CDC on boot enabled, 16 MB flash and OPI PSRAM, matching the currently used N16R8 board. An actual upload replaces the USB diagnostic sketch, so retain the existing sketch for rollback. No upload is performed by creating a pairing key.

The wiring remains PB1→GPIO17, PB0→GPIO16, PA8→GPIO21 and common GND. Keep PA9 disconnected and the radar carrier's switch 2 OFF for ESP control. Both boards need power even when the computer cable is removed.

After a configured firmware upload and restart, the ESP joins Wi-Fi, synchronizes its clock for certificate checks, then polls Haven. Haven requests the diagnostic identity and verifies radar firmware V4.130.4.2 before enabling a scan. Wi-Fi replaces the USB transport; the finite scan protocol and monitoring gaps remain the same.

## Connection loss and recovery

Packets retain byte boundaries, a per-boot identity and monotonically increasing sequence. An identical retry receives the cached commands without replaying observations. Data older than one second, receive overflow, changed retries and out-of-order packets are rejected. A missing polling heartbeat expires the server connection after three seconds. Device-side faults latch a stop and block new scans until the ESP restarts; the existing 25-second scan watchdog also remains.

After a fault or ESP restart, use **Disconnect**, wait for its reader to finish, then **Reset Wi-Fi connection** and restart the ESP. Reset clears the old boot channel but preserves the pairing key. **Revoke Wi-Fi key** removes authorization; create a new key and update the private firmware settings to pair again. Pairing/revocation is refused while a reader is active.

The Wi-Fi sketch intentionally refuses binary `DUMP`. Keep the existing USB capture sketch for raw PA8 acquisition experiments.

## Verification scope

`test_wifi.py` covers authenticated routing, actual HTTPS with a trusted temporary test certificate and hostname verification, plaintext rejection for a simulated remote peer, per-module isolation, command/byte retry behavior, stale/overflow faults and the existing reader's diagnostic handshake with a scripted peer. These are isolated fixtures, not hardware captures. Frontend compilation and firmware compilation do not prove radio connectivity, phone access or delivery timing. Real-device commissioning must verify identity, a finite scan, final radar stop acknowledgment and connection-loss behavior before enabling monitoring.

Phone push alerts are a separate setup described in [WEB-PUSH.md](WEB-PUSH.md); an ESP pairing key does not subscribe a phone.

## Demo networks and captive portals

Use a private 2.4 GHz hotspot or router with both the ESP and Haven laptop connected. Verify that clients can reach each other; some guest networks and hotspots isolate devices. Keep the same configured Haven hostname and certificate valid on that network. The ESP cannot use `127.0.0.1` to reach the laptop. The current firmware also synchronizes time before TLS; provide internet access for that synchronization.

The current sketch has no venue captive-portal login implementation. Wi-Fi association is separate from the portal's web authentication. Venue IT can provide an IoT network or authorize the ESP's MAC address. A permitted portal login implementation would require that venue's actual login flow, cookies and session renewal rules; it cannot be implemented from an SSID and password alone.

After upload, verify the radar version, run a finite scan, check final stop acknowledgement, and test disconnection recovery over the real wireless link. Compilation and pairing-key creation alone do not establish a wireless demo.

## Available devices enrollment

With a blank `HAVEN_DEVICE_TOKEN`, the ESP now announces its MAC-based identity to Haven’s `/api/wifi/discover` endpoint over verified HTTPS. Sensors lists recent requests automatically. Select a registered sensor, disconnect its existing reader, and choose **Add to selected sensor**. Haven generates the key and delivers it only to that ESP’s random enrollment request. The ESP saves the sensor ID and key in Preferences and uses them after restart; no manual key copying is required. Requests expire after 60 seconds without a heartbeat, and the pending list is limited to 32 devices. Changing the configured server prevents reuse of saved enrollment for a different server.

This is discovery of ESPs contacting the configured Haven server, not a router inventory or multicast hostname discovery. The HTTPS server address and its trusted CA still need provisioning in firmware. Existing manual keys remain compatible. The Add action requires workspace sign-in; firmware discovery itself cannot access workspace settings or approve devices. Physical wireless enrollment remains unverified until configured firmware is uploaded and tested.

## Current home commissioning


To launch this home configuration after stopping an existing Haven process, run `tools/run_home_wifi.sh`. Keep the laptop awake, Haven running, and both boards powered. If DHCP changes the laptop address, update the server certificate, allowed host and ESP endpoint together and upload again; a router DHCP reservation can keep the address stable. This LAN setup does not establish internet or phone access.

## Automatic recovery (12 October 2026)

If delivery becomes stale or overflows, the firmware first sends radar stop, blocks further scans and restarts the ESP after ten seconds. The new boot starts at transport sequence zero. Haven can replace an expired/closed Wi-Fi session with a fresh authenticated boot, retires the old session identity, disables monitoring and verifies the radar again. A live session cannot be replaced by another boot. Old queued observations are not presented as new data. CSI calibration is invalidated by the fresh boot and must be repeated. Scans are not automatically resumed.

A deliberate five-second pause of the Haven listener was tested with the physical ESP: both radar verification and CSI returned automatically without a manual ESP reset. This does not prove recovery from every router, internet or captive-portal fault. The initial USB upload interrupted during flashing; the completed retry at 115200 baud passed flash hash verification.

Choosing Disconnect pauses automatic delivery for that sensor during this Haven process. Reset Wi-Fi connection clears that intentional pause. Credential revocation still prevents any delivery. The firmware uses the same private settings header and wiring as before.
