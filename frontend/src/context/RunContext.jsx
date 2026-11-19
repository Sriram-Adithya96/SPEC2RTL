import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, apiUrl, errorMessage } from "../api";
import { useAuth } from "./AuthContext";

const RunContext = createContext(null);

export function RunProvider({ children }) {
  const { user } = useAuth();
  const [runs, setRuns] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [active, setActive] = useState(null);
  const [outputs, setOutputs] = useState({});
  const [starting, setStarting] = useState(false);
  const [banner, setBanner] = useState(null);
  const sourceRef = useRef(null);
  const pollRef = useRef(null);

  async function refreshRuns() {
    try {
      const response = await api.get("/runs");
      const items = response.data.runs || [];
      setRuns(items);
      return items;
    } catch {
      return [];
    }
  }

  function rememberActive(run) {
    setActive(run);
    if (run?.run_id) {
      sessionStorage.setItem("spec2rtl-active-run", run.run_id);
    }
  }

  function stopLiveUpdates() {
    sourceRef.current?.close();
    sourceRef.current = null;
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function startPolling(runId) {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const response = await api.get(`/runs/${runId}`);
        rememberActive(response.data);
        if (["completed", "failed", "cancelled"].includes(response.data.status)) {
          stopLiveUpdates();
          refreshRuns().catch(() => {});
        }
      } catch (error) {
        setBanner(errorMessage(error, "Lost contact with the pipeline."));
      }
    }, 2000);
  }

  function watchRun(runId) {
    stopLiveUpdates();
    const source = new EventSource(apiUrl(`/runs/${runId}/events`));
    sourceRef.current = source;
    source.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "heartbeat" || !payload.metadata) return;
      rememberActive(payload.metadata);
      if (["completed", "failed", "cancelled"].includes(payload.metadata.status)) {
        stopLiveUpdates();
        refreshRuns().catch(() => {});
      }
    };
    source.onerror = () => {
      source.close();
      if (sourceRef.current === source) sourceRef.current = null;
      startPolling(runId);
    };
  }

  // When user signs in, changes, or signs out:
  // Reset active run to null so Dashboard is always clean and outputs are empty!
  useEffect(() => {
    setActiveId(null);
    setActive(null);
    setOutputs({});
    sessionStorage.removeItem("spec2rtl-active-run");
    refreshRuns();
    return () => stopLiveUpdates();
  }, [user?.id]);

  // When a run is activated (either started by user or selected from Run History)
  useEffect(() => {
    if (!activeId) {
      setActive(null);
      return undefined;
    }
    let cancelled = false;
    setOutputs({});
    api
      .get(`/runs/${activeId}`)
      .then((response) => {
        if (cancelled) return;
        rememberActive(response.data);
        if (response.data.status === "running") watchRun(activeId);
      })
      .catch((error) => {
        if (!cancelled) setBanner(errorMessage(error, "Could not open this run."));
      });
    return () => {
      cancelled = true;
      stopLiveUpdates();
    };
  }, [activeId]);

  async function startRun(file) {
    setStarting(true);
    setBanner(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await api.post("/runs", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const metadata = response.data;
      setActiveId(metadata.run_id);
      setActive({
        run_id: metadata.run_id,
        filename: file.name,
        file_size: file.size,
        file_type: file.name.endsWith(".docx") ? ".docx" : ".pdf",
        started_at: new Date().toISOString(),
        status: metadata.status || "running",
        ingestion: "pending",
        agents: {},
      });
      await refreshRuns();
      watchRun(metadata.run_id);
      return metadata.run_id;
    } catch (error) {
      const message = errorMessage(error, "Could not submit this specification.");
      setBanner(message);
      throw new Error(message);
    } finally {
      setStarting(false);
    }
  }

  async function cancelRun(runId = activeId) {
    if (!runId) return;
    try {
      const response = await api.post(`/runs/${runId}/cancel`);
      rememberActive(response.data);
      stopLiveUpdates();
      await refreshRuns();
    } catch (error) {
      setBanner(errorMessage(error, "Could not cancel the pipeline."));
    }
  }

  async function loadOutput(agentId, requestedRunId = activeId) {
    if (!requestedRunId) return null;
    const state = active?.run_id === requestedRunId ? active?.agents?.[agentId] : null;
    const stamp = `${state?.status || ""}|${state?.finished_at || ""}|${state?.message || ""}`;
    const cached = outputs[agentId];
    if (
      cached &&
      cached.runId === requestedRunId &&
      cached.stamp === stamp &&
      state?.status !== "running"
    ) {
      return cached;
    }

    const token = localStorage.getItem("spec2rtl_auth_token");
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const response = await fetch(apiUrl(`/runs/${requestedRunId}/outputs/${agentId}`), { headers });

    if (!response.ok) {
      let detail = "This output is not available yet.";
      try {
        const body = await response.json();
        if (body.detail) detail = body.detail;
      } catch {
        /* The body may be empty. */
      }
      throw new Error(detail);
    }
    const raw = await response.text();
    const parsed = { data: JSON.parse(raw), raw, stamp, runId: requestedRunId };
    if (activeId === requestedRunId) {
      setOutputs((current) => ({ ...current, [agentId]: parsed }));
    }
    return parsed;
  }

  const value = useMemo(
    () => ({
      runs,
      allRuns: runs,
      myRuns: runs,
      scope: "my",
      setScope: () => {},
      active,
      activeId,
      outputs,
      starting,
      banner,
      setBanner,
      setActiveId,
      refreshRuns,
      startRun,
      cancelRun,
      loadOutput,
      running: starting || active?.status === "running",
    }),
    [runs, active, activeId, outputs, starting, banner],
  );

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRuns() {
  const context = useContext(RunContext);
  if (!context) {
    throw new Error("useRuns must be used within RunProvider");
  }
  return context;
}
