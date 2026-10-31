import { useEffect, useState } from "react";
import { resolveUrl } from "./serverConfig";
const sender = "your-sender@example.com";
const gmail = { sender, host: "smtp.gmail.com", username: sender, port: 587, security: "starttls" };
type Settings = { recipient: string; enabled: boolean; hasPassword: boolean; lastDelivery?: string };
export default function EmailSetup() {
  const [settings, setSettings] = useState<Settings>({ recipient: "", enabled: false, hasPassword: false });
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function request(path: string, body?: unknown) {
    const r = await fetch(resolveUrl(path), body === undefined ? undefined : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const value = await r.json();
    if (!r.ok) throw Error(value.error || "Email setup request failed.");
    return value;
  }
  async function load(preserveRecipient = false) {
    try {
      const value = await request("/api/email/settings");
      setSettings(current => ({ recipient: preserveRecipient ? current.recipient : value.recipient || "", enabled: preserveRecipient ? current.enabled : !!value.enabled, hasPassword: !!value.hasPassword, lastDelivery: value.lastDelivery }));
    } catch (e) { setMessage((e as Error).message); }
  }
  useEffect(() => { void load(); }, []);
  async function save(test = false, setupSender = false) {
    setBusy(true); setMessage("");
    try {
      const recipient = settings.recipient.trim();
      if (!recipient) throw Error("Enter the address that should receive alerts first.");
      const secret = setupSender ? password.replace(/\s/g, "") : "";
      if (setupSender && !/^[a-zA-Z0-9]{16}$/.test(secret)) throw Error("Enter the 16-character Google App Password.");
      const value = await request("/api/email/settings", { recipient, enabled: settings.enabled, ...gmail, password: secret });
      setSettings({ recipient: value.recipient, enabled: value.enabled, hasPassword: value.hasPassword, lastDelivery: value.lastDelivery });
      if (setupSender) setPassword("");
      if (test) {
        if (!value.hasPassword) throw Error("Recipient saved. Complete sender setup before sending a test.");
        await request("/api/email/test", {});
        setMessage(`Test email queued for ${recipient}. Check your inbox, then refresh delivery status.`);
      } else {
        setMessage(setupSender ? "Sender authentication saved. Send a test email to verify delivery." : `Alert recipient saved: ${recipient}.${value.hasPassword ? "" : " Sender setup is still required before emails can send."}`);
      }
    } catch (e) { setMessage((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="panel">
    <h2>Email alerts</h2>
    <p>Receive an email when movement triggers an Away alert. Keep Haven running.</p>
    <p className="muted small">Away alert emails are limited to one every 5 minutes. Movement alerts still appear immediately in Haven.</p>
    <p>Alerts are sent from <strong>{sender}</strong>.</p>
    <form onSubmit={e => {
      e.preventDefault();
      const button = (e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
      void save(button?.value === "test");
    }}>
      <label>Send alerts to<input required type="email" autoComplete="email" value={settings.recipient} placeholder="Enter the recipient’s email address" onChange={e => setSettings({ ...settings, recipient: e.target.value })} /></label>
      <p className="muted small">You can change this address anytime. Save to update where future alerts go.</p>
      <label><input type="checkbox" checked={settings.enabled} onChange={e => setSettings({ ...settings, enabled: e.target.checked })} /> Enable Away email alerts</label>
      <div className="button-row">
        <button type="submit" disabled={busy}>Save email setup</button>
        <button type="submit" value="test" disabled={busy || !settings.hasPassword}>Save and send test email</button>
        <button type="button" disabled={busy} onClick={() => void load(true)}>Refresh delivery status</button>
      </div>
    </form>
    <p>Sender: {settings.hasPassword ? "Authentication configured; verify with a test email." : "One-time setup required."}</p>
    {!settings.hasPassword && <details open>
      <summary>Set up sender once on this computer</summary>
      <p>Sign in to Google as {sender}, enable 2-Step Verification, then create an App Password named Haven. Enter it here directly.</p>
      <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">Open Google App Passwords</a>
      <form onSubmit={e => { e.preventDefault(); void save(false, true); }}>
        <label>Gmail App Password<input type="password" required autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="16-character App Password" /></label>
        <button type="submit" disabled={busy}>Save sender authentication</button>
      </form>
      <p className="muted small">The credential stays on this computer. Recipients do not need to supply a password.</p>
    </details>}
    <p role="status">{message}</p>
    <p className="muted small">Delivery: {settings.hasPassword ? settings.lastDelivery || "Not sent yet" : "Blocked — enter the sender’s Gmail App Password above."} Enable Away mode and live monitoring for movement alerts.</p>
  </section>;
}
