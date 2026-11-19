import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, apiUrl, errorMessage } from "../api";

const RunContext = createContext(null);
const STORAGE_KEY = "spec2rtl-my-runs";

function getStoredMyRunIds() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    const activeFromSession = sessionStorage.getItem("spec2rtl-active-run");
    if (activeFromSession && !parsed.includes(activeFromSession)) {
      parsed.unshift(activeFromSession);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed));
      } catch {}
    }
    return parsed;
  } catch {
    return [];
  }
}

function persistMyRunId(runId) {
  try {
    const existing = getStoredMyRunIds();
    if (!existing.includes(runId)) {
      const updated = [runId, ...existing];
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    }
  } catch {}
}

export function RunProvider({ children }) {
  const [allRuns, setAllRuns] = useState([]);
  const [myRunIds, setMyRunIds] = useState(getStoredMyRunIds);
  const [scope, setScope] = useState("my"); // "my" | "all"
  const [activeId, setActiveId] = useState(
    () => sessionStorage.getItem("spec2rtl-active-run") || null,
  );
  const [active, setActive] = useState(null);
  const [outputs, setOutputs] = useState({});
  const [starting, setStarting] = useState(false);
  const [banner, setBanner] = useState(null);
  const sourceRef = useRef(null);
  const pollRef = useRef(null);

  // Filter runs created on this browser
  const myRuns = useMemo(() => {
    return allRuns.filter((r) => myRunIds.includes(r.run_id));
  }, [allRuns, myRunIds]);

  // Runs exposed to views based on scope ("my" by default)
  const runs = scope === "all" ? allRuns : myRuns;

  async function refreshRuns() {
    const response = await api.get("/runs");
    const items = response.data.runs || [];
    setAllRuns(items);
    return items;
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
        if (["completed", "failed"].includes(response.data.status)) {
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
      if (["completed", "failed"].includes(payload.metadata.status)) {
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

  useEffect(() => {
    refreshRuns()
      .then((items) => {
        const storedIds = getStoredMyRunIds();
        // If the activeId is already one of this browser's runs and still valid on the server, keep it
        if (activeId && storedIds.includes(activeId) && items.some((item) => item.run_id === activeId)) {
          return;
        }
        // Otherwise, only auto-select the latest run belonging to THIS browser
        const myLatest = items.find((item) => storedIds.includes(item.run_id));
        if (myLatest) {
          setActiveId(myLatest.run_id);
        } else {
          // Brand new visitor (e.g. friend) starts with a clean slate
          setActiveId(null);
          setActive(null);
          sessionStorage.removeItem("spec2rtl-active-run");
        }
      })
      .catch((error) => {
        setBanner(errorMessage(error, "The API is not reachable."));
      });
    return () => stopLiveUpdates();
  }, []);

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
      const newId = response.data.run_id;
      persistMyRunId(newId);
      setMyRunIds((current) => (current.includes(newId) ? current : [newId, ...current]));
      setOutputs({});
      setActiveId(newId);
      await refreshRuns();
      return response.data;
    } catch (error) {
      const message = errorMessage(error, "The pipeline could not be started.");
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
      return response.data;
    } catch (error) {
      setBanner(errorMessage(error, "Could not cancel the pipeline run."));
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
    const response = await fetch(apiUrl(`/runs/${requestedRunId}/outputs/${agentId}`));
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
      allRuns,
      myRuns,
      scope,
      setScope,
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
    [runs, allRuns, myRuns, scope, active, activeId, outputs, starting, banner],
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
