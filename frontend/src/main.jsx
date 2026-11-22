import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { RunProvider } from "./context/RunContext";
import "./index.css";
import "./glass.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <RunProvider>
          <App />
        </RunProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
