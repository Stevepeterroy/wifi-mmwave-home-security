# Background notification implementation

The optional Web Push adapter encrypts payloads for a browser subscription. It requires server VAPID keys/contact configuration, a service worker and an explicitly subscribed browser on a supported secure origin. No device has been subscribed and no notification has been sent.

Current implementation in webpush.py provides subscription validation, private SQLite storage, deduplicated per-device message queues, five bounded delivery attempts and expiration handling. It accepts recognized HTTPS browser push-provider endpoints and validates encryption key lengths. Queue outcomes distinguish pending, failed, expired and accepted_by_push_service. A push service accepting a message does not establish that the device received it, displayed it or that a person read it.

Configure server-only HAVEN_VAPID_PRIVATE_KEY, HAVEN_VAPID_PUBLIC_KEY and HAVEN_VAPID_SUBJECT for the adapter. Private keys are never intended for browser exposure; the public key is used when subscribing. The requirements file pins the Python transport dependencies. Key generation, service-worker subscription UI, server routing and Away/trial scheduler wiring remain follow-up implementation work. This adapter alone does not enable background reminders.

Tests use synthetic subscriptions and injected senders; they make no external requests. Real HTTPS phone deployment, delivery, expired-device behavior and notification permission handling need device-level verification. Existing finite scans still have monitoring gaps, and a push alert cannot improve unvalidated person/activity classification.

References: [pywebpush implementation](https://github.com/web-push-libs/pywebpush), [browser subscription API](https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe).

Runtime check: pywebpush 2.1.2 is installed and pip dependency checks pass. Its call signature supports the adapter arguments. The existing diagnostic Python uses LibreSSL 2.8.3, while installed urllib3 v2 requires OpenSSL 1.1.1 or newer; real outbound delivery remains unsuitable for verification until the service uses a supported TLS runtime. Do not suppress this warning or downgrade transport merely to claim success.

Runtime follow-up: Haven now runs in its own Python 3.13 environment with OpenSSL 3.6.4. Imports pass with warnings treated as errors and dependency checks pass. All 38 backend tests pass on this runtime, which exposes unclosed SQLite connection warnings in older service/auth/test paths; connection cleanup remains follow-up work. The supported TLS runtime resolves the prior LibreSSL limitation, but real push delivery remains unverified.

Database cleanup follow-up: service/authentication/test connection lifetimes have been corrected. All 40 backend tests pass with ResourceWarning reporting enabled and no unclosed-connection warnings.

Subscription follow-up: Setup now provides enable/disable controls, with explicit browser permission and secure-context checks. A push service worker displays received notifications and reopens the same workspace. Authenticated APIs save/remove subscriptions and expose aggregate delivery status without returning subscription endpoints. Real HTTP fixture tests cover registration, removal and anonymous rejection. No real browser subscription or notification exists. Event/scheduler wiring is still pending.

Scheduler wiring: a separate service thread schedules due trial messages from three days before expiry onward at the configured interval, with durable per-device deduplication. Pending cancellation continues reminders. Verified cancellation with a nonblank reference, removal or moving a trial outside its reminder window cancels pending messages. New persisted live Away events queue review alerts; recorded replay is excluded. Network delivery runs separately from acquisition and requires configured keys plus an enrolled workspace. The service must remain running; delivery on a powered-off or disconnected phone is not guaranteed. Messages already accepted by the provider or in flight cannot be recalled by changing cancellation status. Three scheduler tests cover repeated/restart scheduling, pending/verified transitions, reminder-window boundaries and removed trials. Real device delivery remains unverified.

## Generate deployment keys

Run `.venv/bin/python configure_push.py --subject mailto:YOUR_ACTUAL_CONTACT` with your real contact URI. The utility writes a private PEM, matching public key and subject into data/push with private file permissions. It refuses to replace existing files because changing signing keys can invalidate current browser subscriptions. No production keys have been generated in this session.

Configure HAVEN_VAPID_PRIVATE_KEY as the absolute path to vapid-private.pem, HAVEN_VAPID_PUBLIC_KEY as the text in vapid-public.txt, and HAVEN_VAPID_SUBJECT as the text in vapid-subject.txt. Use the authenticated TLS deployment described in SECURE-DEPLOYMENT.md for phone access. Start the service with these variables, sign in on the target browser, then explicitly enable background notifications in Setup. A service-worker registration or subscription response is not delivery proof: verify an actual notification on that device before relying on it.

Local cryptographic verification now exercises the actual installed pywebpush encryption and VAPID authorization with ephemeral keys and a mocked HTTP transport. The subscriber private key successfully decrypts the generated payload. Two key-generation tests check matching keys, private permissions, refusal to overwrite and contact validation. No external requests, production keys or real subscriptions were created.

Setup now shows aggregate delivery prerequisites and queue outcomes from the service. Counts cover all registered devices in the workspace, not just the current browser. Endpoints and encryption keys are not exposed in these totals. No receive/read acknowledgments are claimed.

Message freshness: queue rows now retain creation/expiry times. Delivery expires pending messages outside their useful lifetime before sending; trial message lifetime is at most its repeat interval or five minutes. Legacy pending rows without timing are expired rather than treated as fresh. Each sender rechecks queue/subscription state so cancellation or subscription expiration during a batch skips later attempts. Away notification bodies include the observed event time. In-flight messages still cannot be recalled. An additional test verifies that expired messages never reach the transport.
# User deferral — 10 October 2026

Phone-alert setup is deferred at the user's request. Keep existing implementation available, but leave deployment keys, device permission/subscription and real delivery testing for later. This deferral does not prevent local dashboard, GLB or ESP transport work.
