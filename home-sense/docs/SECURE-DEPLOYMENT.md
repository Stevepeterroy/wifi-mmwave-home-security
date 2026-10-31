# Sign-in and future phone access

Haven remains local-only by default. No password has been chosen for the user's production workspace and no remote listener has been enabled.

## Local enrollment

Open Sensors → Set up sign-in for Wi-Fi pairing. Choose and confirm your own password. The app stores a random salt and PBKDF2-HMAC-SHA256 digest (600,000 iterations), not the password. This choice follows the available runtime's supported primitives and the [OWASP password-storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

Once enrolled, home/sensor/event/API access requires sign-in. Sessions use a random HttpOnly, SameSite=Strict cookie with a 12-hour lifetime. Restarting the service requires signing in again. Sign-out revokes the session. Five failed login attempts pause further attempts for 15 minutes. Workspace enrollment is allowed only from the local computer and only once.

The agent did not create a production password. Password enrollment/login were tested only in isolated temporary test databases.

## Deployment prerequisites

The service will refuse a non-loopback listener unless all are provided:

- A locally enrolled workspace password.
- `HAVEN_TLS_CERT` and `HAVEN_TLS_KEY` pointing to the deployment's certificate and private key.
- `HAVEN_ALLOWED_HOSTS` listing the exact allowed HTTP Host values, including port when applicable.
- An explicit `HAVEN_BIND` address, such as the private LAN interface.

TLS is enabled with TLS 1.2 minimum and cookies gain the Secure flag. Use a normally trusted certificate for the deployed hostname. Certificate validation must not be bypassed to test the app.

The default launcher sets none of these remote options. Do not change the listener merely to bypass the current browser automation denial; deployment is separate work requiring its own account/domain/network evidence.

## Remaining verification

Real browser sign-in, phone access, trusted TLS deployment and remote push are not verified. Shared scan storage now provides authenticated metadata and binary retrieval, with content hash verification. Actual phone retrieval and rendering remain unverified.
