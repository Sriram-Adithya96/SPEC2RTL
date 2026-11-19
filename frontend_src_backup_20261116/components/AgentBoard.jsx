import {
  ChevronDown,
  Code2,
  Cpu,
  FileSearch,
  FileText,
  Loader2,
  Network,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useRuns } from "../context/RunContext";
import { AGENTS, formatTime } from "../lib/format";
import DecompositionView from "../views/DecompositionView";
import ErrorBanner from "./ErrorBanner";
import DescriptionView from "../views/DescriptionView";
import PseudocodeView from "../views/PseudocodeView";
import RTLResultsView from "../views/RTLResultsView";
import RTLVerificationView from "../views/RTLVerificationView";
import ReflectionView from "../views/ReflectionView";
import UnderstandingView from "../views/UnderstandingView";
import JsonViewer from "./JsonViewer";
import StatusBadge from "./StatusBadge";

const ICONS = {
  understanding: FileSearch,
  decomposer: Network,
  description: FileText,
  pseudocode: Code2,
  rtl_generation: Cpu,
  rtl_verification: ShieldCheck,
  reflection: Sparkles,
};

/** Map agent status → pipeline node styles */
function nodeStyle(status) {
  switch (status) {
    case "completed":
      return {
        border: "2px solid #22c55e",
        bg: "#dcfce7",
        icon: "#15803d",
        connector: "#22c55e",   // filled green connector after completed node
        pulse: false,
      };
    case "running":
      return {
        border: "2px solid #7540C5",
        bg: "#EDE8FA",
        icon: "#7540C5",
        connector: "#7540C5",   // shimmer handled by connector-running class
        pulse: true,
      };
    case "failed":
      return {
        border: "2px solid #ef4444",
        bg: "#fee2e2",
        icon: "#b91c1c",
        connector: "#ef4444",   // red connector after failed node
        pulse: false,
      };
    case "skipped":
      return {
        border: "2px dashed #C5A6F2",  // dashed border = skipped
        bg: "#F8F5FF",
        icon: "#A879E5",
        connector: "#C5A6F2",           // soft purple connector after skipped node
        pulse: false,
      };
    default: // pending
      return {
        border: "2px solid #D8CCF0",
        bg: "rgba(248,245,255,0.6)",
        icon: "#C5A6F2",
        connector: "#D8CCF0",
        pulse: false,
      };
  }
}

/** Horizontal pipeline node strip */
function PipelineNodes({ run, expanded, onSelect }) {
  return (
    <div className="mb-5 overflow-x-auto">
      <div className="flex w-full min-w-max items-start gap-0 px-1 py-3">
        {AGENTS.map((agent, index) => {
          const state = run?.agents?.[agent.id] || { status: "pending" };
          const style = nodeStyle(state.status || "pending");
          const Icon = ICONS[agent.id];
          const isActive = expanded === agent.id;

          return (
            <div
              key={agent.id}
              className={`flex items-start ${index < AGENTS.length - 1 ? "flex-1" : ""}`}
            >
              {/* Node button */}
              <button
                type="button"
                onClick={() => onSelect(isActive ? null : agent.id)}
                title={agent.name}
                aria-label={`${agent.name} — ${state.status || "pending"}`}
                className="flex flex-col items-center gap-1.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5] focus-visible:ring-offset-2"
              >
                {/* Circle */}
                <div
                  className={style.pulse ? "node-running" : ""}
                  style={{
                    width: 46,
                    height: 46,
                    borderRadius: "50%",
                    border: style.border,
                    background: style.bg,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    outline: isActive ? "3px solid #7540C5" : "none",
                    outlineOffset: 2,
                    transition: "outline 150ms ease, box-shadow 150ms ease",
                    flexShrink: 0,
                  }}
                >
                  <Icon size={18} color={style.icon} />
                </div>
                {/* Label */}
                <div className="text-center" style={{ width: 64 }}>
                  <div className="text-[9px] font-bold text-muted">
                    {String(agent.number).padStart(2, "0")}
                  </div>
                  <div
                    className="text-[9px] font-semibold leading-tight text-indigo"
                    style={{ hyphens: "auto" }}
                  >
                    {agent.name.replace(" Agent", "")}
                  </div>
                </div>
              </button>

              {/* Connector line between nodes — wider, filled to show pipeline progress */}
              {index < AGENTS.length - 1 && (
                <div
                  className={state.status === "running" ? "connector-running" : ""}
                  style={{
                    flex: 1,
                    minWidth: 24,
                    height: 3,
                    marginTop: 22,
                    background: state.status === "running" ? undefined : style.connector,
                    borderRadius: 3,
                    flexShrink: 0,
                    opacity: state.status === "pending" ? 0.4 : 1,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AgentBoard({ run }) {
  const { outputs, loadOutput } = useRuns();
  const runId = run?.run_id;
  const [expanded, setExpanded] = useState(null);
  const [mode, setMode] = useState("formatted");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const loadRef = useRef(loadOutput);
  loadRef.current = loadOutput;

  useEffect(() => {
    setExpanded(null);
    setError("");
  }, [run?.run_id]);

  const expandedState = expanded ? run?.agents?.[expanded] : null;
  const outputStamp = `${expanded || ""}|${expandedState?.status || ""}|${expandedState?.finished_at || ""}|${expandedState?.message || ""}`;

  useEffect(() => {
    if (!expanded) return undefined;
    const status = expandedState?.status;
    if (!status || status === "pending" || status === "skipped") return undefined;
    let cancelled = false;
    setLoading(true);
    setError("");
    (async () => {
      try {
        await loadRef.current(expanded, runId);
      } catch (loadError) {
        if (!cancelled) setError(loadError.message || "Could not load this output.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [outputStamp, expanded, runId]);

  function handleSelect(agentId) {
    setError("");
    setMode("formatted");
    setExpanded(agentId);
  }

  return (
    <div>
      {/* Pipeline node visualization */}
      <div className="glass mb-4 overflow-hidden px-4 py-2">
        <PipelineNodes run={run} expanded={expanded} onSelect={handleSelect} />
      </div>

      {/* Agent accordion cards */}
      <div className="grid gap-3">
        {AGENTS.map((agent) => {
          const state = run?.agents?.[agent.id] || { status: "pending", components: [] };
          const open = expanded === agent.id;
          const Icon = ICONS[agent.id];
          const cachedOutput = outputs[agent.id];
          const output = cachedOutput?.runId === runId ? cachedOutput : null;
          const components = state.components || [];
          const ns = nodeStyle(state.status || "pending");

          return (
            <article
              key={agent.id}
              className="glass overflow-hidden"
            >
              {/* Left status rail — coloured vertical stripe keyed to agent status */}
              <div
                aria-hidden="true"
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: 4,
                  background: ns.border.replace("2px solid ", "").replace("2px dashed ", ""),
                  borderRadius: "20px 0 0 20px",
                  opacity: state.status === "pending" ? 0.35 : 0.9,
                }}
              />

              {/* Header button */}
              <button
                type="button"
                className="flex w-full items-start gap-4 pl-6 pr-4 py-4 text-left md:pl-7 md:pr-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#7540C5]"
                aria-expanded={open}
                onClick={() => handleSelect(open ? null : agent.id)}
              >
                {/* Agent icon */}
                <div
                  style={{
                    width: 46,
                    height: 46,
                    borderRadius: 14,
                    background: ns.bg,
                    border: ns.border,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Icon size={18} color={ns.icon} />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold tracking-wide text-[#A879E5]">
                    Agent {agent.number}
                  </div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2">
                    <h3 className="font-bold text-indigo">{agent.name}</h3>
                    <StatusBadge status={state.status || "pending"} />
                  </div>
                  <p className="mt-1 text-sm text-muted">{agent.description}</p>
                  <p className="mt-1 text-xs text-muted">
                    {state.started_at ? `Started ${formatTime(state.started_at)}` : "Not started"}
                    {state.finished_at ? ` · Finished ${formatTime(state.finished_at)}` : ""}
                  </p>
                </div>

                <ChevronDown
                  size={18}
                  className={`mt-1 shrink-0 text-[#7540C5] transition ${open ? "rotate-180" : ""}`}
                />
              </button>

              {/* Running message */}
              {state.message && state.status === "running" && (
                <p className="px-5 pb-3 text-sm text-[#4A3566]">{state.message}</p>
              )}

              {/* RTL sub-statuses */}
              {agent.id === "rtl_generation" && (
                <div className="flex flex-wrap gap-2 px-5 pb-4">
                  {[
                    ["Components", state.component_generation_status],
                    ["Interfaces", state.interface_validation_status],
                    ["Integration", state.integration_status],
                  ].map(([label, status]) =>
                    status ? (
                      <div key={label} className="flex items-center gap-2 rounded-xl bg-[#F8F5FF] px-3 py-2">
                        <span className="text-xs font-semibold text-muted">{label}</span>
                        <StatusBadge status={status} />
                      </div>
                    ) : null
                  )}
                </div>
              )}

              {/* Component list */}
              {components.length > 0 && (
                <div className="grid gap-2 px-5 pb-4">
                  {components.map((component, index) => (
                    <div
                      key={`${component.name}-${index}`}
                      className="flex items-center justify-between gap-3 rounded-xl bg-[#F8F5FF] px-3 py-2"
                    >
                      <span className="text-sm font-medium text-indigo">{component.name}</span>
                      <div className="flex flex-wrap justify-end gap-2">
                        {component.generation_status && (
                          <StatusBadge status={component.generation_status} />
                        )}
                        {component.interface_validation_status && (
                          <StatusBadge status={component.interface_validation_status} />
                        )}
                        {!component.generation_status && !component.interface_validation_status && (
                          <StatusBadge status={component.status || "pending"} />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Error banner — deduplicated display; stored data unchanged */}
              {state.error && <ErrorBanner error={state.error} className="mx-5 mb-4" />}

              {/* Expandable output panel */}
              <div className={`expand-panel ${open ? "open" : ""}`}>
                <div>
                  <div className="border-t border-[#E9DDFB] bg-[#F8F5FF]/80 px-4 py-4 md:px-5">
                    {state.status === "pending" && (
                      <p className="text-sm text-muted">This agent has not run yet.</p>
                    )}
                    {state.status === "skipped" && (
                      <p className="text-sm text-muted">
                        This agent did not run because an earlier stage failed.
                      </p>
                    )}
                    {state.status !== "pending" && state.status !== "skipped" && (
                      <>
                        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                          {/* View toggle */}
                          <div className="flex rounded-xl bg-[#E9DDFB] p-1">
                            {["formatted", "raw"].map((item) => (
                              <button
                                key={item}
                                type="button"
                                onClick={() => setMode(item)}
                                className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
                                  mode === item
                                    ? "bg-white text-[#7540C5] shadow-card"
                                    : "text-[#4A3566]"
                                }`}
                              >
                                {item === "formatted" ? "Formatted View" : "Raw JSON View"}
                              </button>
                            ))}
                          </div>
                          {/* Download link */}
                          {runId && (
                            <a
                              href={`/api/runs/${runId}/download/${agent.file}`}
                              className="text-xs font-semibold text-[#7540C5] hover:text-[#35145D]"
                            >
                              Download {agent.file}
                            </a>
                          )}
                        </div>

                        {loading && !output && (
                          <p className="flex items-center gap-2 text-sm text-muted">
                            <Loader2 size={16} className="animate-spin" />
                            Loading output
                          </p>
                        )}
                        {error && <p className="text-sm text-[#8F1D1D]">{error}</p>}
                        {output && mode === "formatted" && (
                          <FormattedOutput
                            agentId={agent.id}
                            output={output}
                            outputs={outputs}
                            runId={runId}
                          />
                        )}
                        {output && mode === "raw" && (
                          <JsonViewer
                            raw={output.raw}
                            filename={agent.file}
                            downloadHref={
                              runId
                                ? `/api/runs/${runId}/download/${agent.file}`
                                : undefined
                            }
                          />
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

function FormattedOutput({ agentId, output, outputs, runId }) {
  const data = output?.data;
  if (agentId === "understanding") return <UnderstandingView data={data} />;
  if (agentId === "decomposer") return <DecompositionView data={data} />;
  if (agentId === "description") return <DescriptionView data={data} />;
  if (agentId === "pseudocode") return <PseudocodeView data={data} runId={runId} />;
  if (agentId === "rtl_generation") return <RTLResultsView data={data} runId={runId} />;
  if (agentId === "rtl_verification") return <RTLVerificationView data={data} />;
  if (agentId === "reflection") return <ReflectionView data={data} runId={runId} />;
  return <p className="text-sm text-muted">No formatted view is available for this output.</p>;
}

function RTLStat({ label, value }) {
  return (
    <div className="rounded-xl bg-[#F8F5FF] px-3 py-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 text-xl font-bold text-indigo">{value}</div>
    </div>
  );
}

function IssueList({ title, items, warning = false }) {
  const borderColor = warning ? "border-[#E7D7A1]" : "border-[#F3C0C0]";
  const background = warning ? "bg-[#FFF8EA]" : "bg-[#FFF6F6]";
  const textColor = warning ? "text-[#7A5B12]" : "text-[#8F1D1D]";

  return (
    <section className={`rounded-2xl border ${borderColor} ${background} p-4`}>
      <h4 className={`mb-2 text-sm font-bold ${textColor}`}>{title}</h4>
      {items.length === 0 ? (
        <p className="text-sm text-muted">None recorded.</p>
      ) : (
        <ul className={`list-disc space-y-1 pl-5 text-sm ${textColor}`}>
          {items.map((item, index) => (
            <li key={`${index}-${String(item)}`}>
              {typeof item === "string" ? item : JSON.stringify(item)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
