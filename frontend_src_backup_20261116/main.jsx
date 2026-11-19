import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { RunProvider } from "./context/RunContext";
import "./index.css";
import "./glass.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <RunProvider>
        <App />
      </RunProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
