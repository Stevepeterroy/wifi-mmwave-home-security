import { useEffect, useRef, useState } from "react";
import { Wifi, Usb, RefreshCw } from "lucide-react";
import { resolveUrl, isAndroid } from "./serverConfig";

type Job = {id: string; state: string; phase: string; message: string; backupVerified: boolean; progressPercent?: number | null; elapsedSeconds?: number; phaseElapsedSeconds?: number; stalled?: boolean};
type Status = {ssid: string; host: string; hasPassword: boolean; configured: boolean; toolsReady: boolean; ports: {port: string; name: string}[]; job: Job | null};
async function request(body?: unknown, flash = false): Promise<any> {
  const response = await fetch(resolveUrl(flash ? "/api/esp/flash" : "/api/esp/setup"), body === undefined ? undefined : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw Error(data.error || "ESP setup request failed");
  return data;
}
export default function EspSetup() {
  const [status, setStatus] = useState<Status | null>(null);
  const [ssid, setSsid] = useState("");
  const [password, setPassword] = useState("");
  const [host, setHost] = useState("");
  const [openNetwork, setOpenNetwork] = useState(false);
  const [port, setPort] = useState("");
  const [mode, setMode] = useState<"csi_only" | "csi_radar">("csi_radar");
  const [wiringConfirmed, setWiringConfirmed] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const initialized = useRef(false);
  const local = !isAndroid() && ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const running = status?.job?.state === "running";
  const dirty = !!status && (ssid !== status.ssid || host !== status.host || !!password || openNetwork === status.hasPassword);
  async function refresh() {
    try {
      const value: Status = await request(); setStatus(value);
      if (!initialized.current) {setSsid(value.ssid); setHost(value.host); setOpenNetwork(!value.hasPassword); initialized.current = true;}
      setPort(current => value.ports.some(p => p.port === current) ? current : "");
    } catch (e) {setError((e as Error).message);}
  }
  useEffect(() => {if (local) void refresh();}, [local]);
  useEffect(() => {
    if (!local) return;
    const timer = window.setInterval(() => void refresh(), running ? 1500 : 5000);
    return () => window.clearInterval(timer);
  }, [local, running]);
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const value = await request({ssid, password, host, openNetwork});
      setPassword(""); setConfirmed(false); await refresh();
      setMessage(value.restartRequired ? "Settings saved. Restart Haven before flashing to activate the new TLS endpoint." : "Wi-Fi settings saved privately. Flash the ESP below to apply them; saving alone does not change its network.");
    } catch (e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  async function flash() {
    setBusy(true); setError(""); setMessage("");
    try {await request({port, confirm: confirmed, mode, wiringConfirmed}, true); setConfirmed(false); await refresh();}
    catch (e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  return <section className="panel esp-setup" aria-labelledby="esp-setup-title">
    <div className="esp-setup-heading"><Wifi size={23}/><div><h2 id="esp-setup-title">Set up an ESP32</h2><p className="muted">Home router today. Demo router tomorrow.</p></div></div>
    {!local ? <p>Open Haven on the server laptop at localhost to save Wi-Fi credentials and use the USB flasher. Phone and remote flashing are not enabled.</p> : <>
      <form onSubmit={save} className="esp-network-form">
        <h3>1. Wi-Fi connection</h3>
        <p>Use a 2.4 GHz network shared by the ESP and laptop. Captive-portal login is not supported.</p>
        <div className="form-grid">
          <label>Wi-Fi name (SSID)<input value={ssid} onChange={e => setSsid(e.target.value)} autoComplete="off" maxLength={32} required disabled={!!running || busy}/></label>
          <label>Wi-Fi password<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" maxLength={63} disabled={openNetwork || !!running || busy} placeholder={status?.hasPassword ? "Saved password — leave blank to keep" : "Enter Wi-Fi password"}/></label>
          <label>Laptop Wi-Fi IPv4 address<input value={host} onChange={e => setHost(e.target.value)} placeholder="192.168.1.19" autoComplete="off" required disabled={!!running || busy}/></label>
        </div>
        <label className="esp-confirm"><input type="checkbox" checked={openNetwork} onChange={e => setOpenNetwork(e.target.checked)} disabled={!!running || busy}/>This is an open network without a password</label>
        <p className="muted small">Credentials are saved privately on this laptop and included in its ESP firmware. They are never returned by this form. Changing the laptop IP updates the device TLS certificate; other ESPs on the old endpoint will need reconfiguration.</p>
        <button type="submit" disabled={!status || busy || !!running}>Save Wi-Fi settings</button>
      </form>
      <div className="esp-flasher">
        <h3><Usb size={18}/> 2. Install Haven firmware</h3>
        <p>Connect an <strong>ESP32-S3 N16R8</strong> with a data-capable USB cable. Select CSI only, or combine CSI with RD-60 UART diagnostics and available radar data. This does not repair a silent PA8 output.</p>
        <label>Firmware mode<select value={mode} onChange={e => {setMode(e.target.value as "csi_only" | "csi_radar");setConfirmed(false);}} disabled={!!running || busy}>
          <option value="csi_radar">Wi-Fi CSI + RD-60 mmWave</option><option value="csi_only">Wi-Fi CSI only (no radar GPIOs)</option>
        </select></label>
        {mode === "csi_radar" && <label className="esp-confirm"><input type="checkbox" checked={wiringConfirmed} onChange={e => setWiringConfirmed(e.target.checked)} disabled={!!running || busy}/>Radar PB0 → ESP GPIO16, PB1 → GPIO17, PA8 → GPIO21, common GND; all kit UART DIP switches OFF. Both boards must be powered.</label>}
        <div className="button-row"><label>ESP USB port<select value={port} onChange={e => setPort(e.target.value)} disabled={!!running || busy}><option value="">Choose the ESP32 USB port</option>{status?.ports.map(p => <option key={p.port} value={p.port}>{p.name} · {p.port}</option>)}</select></label><button onClick={() => void refresh()} disabled={!!running || busy}><RefreshCw size={15}/>Refresh ports</button></div>
        {!status?.toolsReady && <p className="esp-warning">Requires Arduino IDE, its Espressif ESP32 board package, and esptool on this laptop. No browser extension or firmware download service is used.</p>}
        <label className="esp-confirm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} disabled={!!running || busy}/>I selected the ESP32-S3 and understand that flashing replaces its firmware and interrupts sensing.</label>
        {dirty && <p className="muted small">Save your Wi-Fi changes before flashing.</p>}
        <button onClick={() => void flash()} disabled={!status?.configured || !status?.toolsReady || !port || !confirmed || (mode === "csi_radar" && !wiringConfirmed) || dirty || busy || !!running}>Back up &amp; flash ESP32</button>
        <p className="muted small">The first 4 MiB are backed up and size-checked before any write. Keep USB connected throughout; backup can take several minutes. Pairing happens afterward under Available devices.</p>
        {status?.job && <div className="esp-job" role="status"><strong>{status.job.phase}</strong><p>{status.job.message}</p><span>{status.job.backupVerified ? "Pre-flash backup verified." : status.job.phase.startsWith("Backing") && status.job.state === "running" ? "Backup is being read; verification happens after it reaches 100%." : "No verified backup yet."}</span>
          <span className="esp-progress-text">{status.job.progressPercent != null ? `${status.job.progressPercent.toFixed(1)}% of this phase · ` : ""}{status.job.elapsedSeconds != null ? `${Math.floor(status.job.elapsedSeconds/60)}m ${status.job.elapsedSeconds%60}s elapsed` : "Detailed timing is available after Haven restarts."}</span>
          {status.job.phase.startsWith("Backing") && status.job.state === "running" && <p className="muted small">A 4 MiB backup at the safe 115200 baud commonly takes 6–8 minutes. Do not unplug it while progress is increasing.</p>}
          {status.job.stalled && <p className="esp-warning" role="alert">No recent progress output. The job may be stalled; keep USB connected while checking its cable and port. Do not start another flash.</p>}
          {status.job.state === "running" && (status.job.progressPercent != null ? <progress max="100" value={status.job.progressPercent} aria-label="ESP firmware phase progress"/> : <progress aria-label="ESP firmware job in progress"/>)}</div>}
      </div>
      {message && <p role="status">{message}</p>}{error && <p role="alert" className="esp-warning">{error}</p>}
    </>}
  </section>;
}
