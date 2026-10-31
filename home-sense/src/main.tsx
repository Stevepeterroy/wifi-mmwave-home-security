import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./style.css";
import { isAndroid, getServerUrl } from "./serverConfig";
import ServerSetup from "./ServerSetup";

function Root() {
  // On Android, show the server setup screen if no server URL is configured yet
  const [ready, setReady] = useState(!isAndroid() || !!getServerUrl());

  if (!ready) {
    return <ServerSetup onConfigured={() => setReady(true)} />;
  }

  return <App />;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
