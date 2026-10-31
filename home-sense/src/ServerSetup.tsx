import { useState } from "react";
import { Wifi } from "lucide-react";
import { setServerUrl, getServerUrl, DEFAULT_SERVER_URL } from "./serverConfig";

interface Props {
  onConfigured: () => void;
}

export default function ServerSetup({ onConfigured }: Props) {
  const [url, setUrl] = useState(
    getServerUrl() || DEFAULT_SERVER_URL,
  );
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setTesting(true);
    const cleaned = url.replace(/\/$/, "");
    try {
      const r = await fetch(cleaned + "/api/state", { signal: AbortSignal.timeout(8000) });
      if (!r.ok) throw new Error("Server responded with " + r.status);
      setServerUrl(cleaned);
      onConfigured();
    } catch (err) {
      setError(
        "Could not reach the Haven server at that address.\n" +
          "• Make sure the Cloudflare tunnel or Python server is running\n" +
          "• Check the server URL\n" +
          "• Error: " + (err instanceof Error ? err.message : String(err)),
      );
    } finally {
      setTesting(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "#0d1f1c",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        zIndex: 9999,
        fontFamily: "system-ui, sans-serif",
        color: "#e8e6df",
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          background: "#1a3a33",
          borderRadius: 16,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: "1.5rem",
        }}
      >
        <Wifi size={28} color="#4ecda4" />
      </div>

      <h1 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: "0.5rem", textAlign: "center" }}>
        Connect to Haven server
      </h1>
      <p style={{ color: "#8a9e99", fontSize: "0.9rem", textAlign: "center", marginBottom: "2rem", lineHeight: 1.5 }}>
        Enter the IP address of the Mac running your Haven Python server.
        Both devices must be on the same WiFi network.
      </p>

      <form onSubmit={handleSubmit} style={{ width: "100%", maxWidth: 360 }}>
        <label style={{ display: "block", fontSize: "0.8rem", color: "#8a9e99", marginBottom: "0.4rem" }}>
          Server address
        </label>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="http://192.168.1.42:8768"
          required
          style={{
            width: "100%",
            padding: "0.85rem 1rem",
            background: "#1a3a33",
            border: "1px solid #2a4a42",
            borderRadius: 10,
            color: "#e8e6df",
            fontSize: "1rem",
            marginBottom: "1rem",
            boxSizing: "border-box",
            outline: "none",
          }}
        />

        {error && (
          <p
            style={{
              color: "#f87171",
              fontSize: "0.82rem",
              marginBottom: "1rem",
              whiteSpace: "pre-line",
              lineHeight: 1.6,
            }}
          >
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={testing}
          style={{
            width: "100%",
            padding: "0.85rem",
            background: testing ? "#1a3a33" : "#4ecda4",
            color: testing ? "#4ecda4" : "#0d1f1c",
            border: "none",
            borderRadius: 10,
            fontWeight: 700,
            fontSize: "1rem",
            cursor: testing ? "default" : "pointer",
          }}
        >
          {testing ? "Connecting…" : "Connect"}
        </button>

        <p style={{ color: "#5a7a74", fontSize: "0.78rem", textAlign: "center", marginTop: "1.5rem", lineHeight: 1.6 }}>
          To find your Mac's IP: System Settings → Wi-Fi → Details
          {"\n"}The default server port is 8768.
        </p>
      </form>
    </div>
  );
}
