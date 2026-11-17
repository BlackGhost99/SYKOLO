import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";
import {installCommercialReadOnlyNotice} from "./commercial-read-only.js";
installCommercialReadOnlyNotice(window);
createRoot(document.getElementById("root")).render(<App />);

if(typeof window!=="undefined" && "serviceWorker" in navigator && (location.protocol==="https:"||location.hostname==="localhost"||location.hostname==="127.0.0.1")){
  window.addEventListener("load",()=>navigator.serviceWorker.register("/service-worker.js").catch(()=>{}));
}
