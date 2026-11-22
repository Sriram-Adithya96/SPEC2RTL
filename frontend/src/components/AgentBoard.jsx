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
import { apiUrl } from "../api";
import { useRuns } from "../context/RunContext";
import { AGENTS, formatTime, formatTokens, formatTokensCompact, getAgentUsage } from "../lib/format";
import DecompositionView from "../views/DecompositionView";
import DescriptionView from "../views/DescriptionView";
import PseudocodeView from "../views/PseudocodeView";
import ReflectionView from "../views/ReflectionView";
import RTLResultsView from "../views/RTLResultsView";
import RTLVerificationView from "../views/RTLVerificationView";
import UnderstandingView from "../views/UnderstandingView";
import ErrorBanner from "./ErrorBanner";
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
    case "passed":
    case "completed":
      return {
        border: "1.5px solid var(--ok, #4ade80)",
        bg: "rgba(74, 222, 128, 0.12)",
        icon: "var(--ok, #4ade80)",
        connector: "var(--ok, #4ade80)",
        pulse: false,
      };
    case "running":
      return {
        border: "1.5px solid var(--acc, #7dd3fc)",
        bg: "rgba(125, 211, 252, 0.15)",
        icon: "var(--acc, #7dd3fc)",
        connector: "var(--acc, #7dd3fc)",
        pulse: true,
      };
    case "cancelled":
    case "failed":
      return {
        border: "1.5px solid var(--bad, #f87171)",
        bg: "rgba(248, 113, 113, 0.15)",
        icon: "var(--bad, #f87171)",
        connector: "var(--bad, #f87171)",
        pulse: false,
      };
    case "skipped":
      return {
        border: "1.5px dashed var(--warn, #fbbf24)",
        bg: "rgba(251, 191, 36, 0.08)",
        icon: "var(--warn, #fbbf24)",
        connector: "var(--line, #243044)",
        pulse: false,
      };
    default: // pending
      return {
        border: "1.5px solid var(--line, #243044)",
        bg: "rgba(16, 22, 32, 0.5)",
        icon: "var(--mute, #7d8aa3)",
        connector: "var(--line, #243044)",
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
          const agentUsage = getAgentUsage(run, agent.id);

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
                className="flex flex-col items-center gap-1.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)] focus-visible:ring-offset-2"
              >
                {/* Circle */}
                <div
                  className={style.pulse ? "node-running" : ""}
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    border: style.border,
                    background: style.bg,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    outline: isActive ? "2px solid var(--acc2, #a78bfa)" : "none",
                    outlineOffset: 2,
                    transition: "outline 150ms ease, box-shadow 150ms ease",
                    flexShrink: 0,
                  }}
                >
                  <Icon size={18} color={style.icon} />
                </div>
                {/* Label */}
                <div className="text-center" style={{ width: 64 }}>
                  <div className="text-[9px] font-bold font-mono text-[var(--mute)]">
                    {String(agent.number).padStart(2, "0")}
                  </div>
                  <div
                    className="text-[9px] font-semibold font-mono leading-tight text-[var(--text)]"
                    style={{ hyphens: "auto" }}
                  >
                    {agent.name.replace(" Agent", "")}
                  </div>
                  {agentUsage?.total_tokens > 0 && (
                    <div className="mt-0.5 text-[8.5px] font-mono font-bold text-[var(--acc)]">
                      ⚡{formatTokensCompact(agentUsage.total_tokens)}
                    </div>
                  )}
                </div>
              </button>

              {/* Connector line between nodes */}
              {index < AGENTS.length - 1 && (
                <div
                  className={state.status === "running" ? "connector-running" : ""}
                  style={{
                    flex: 1,
                    minWidth: 24,
                    height: 2,
                    marginTop: 22,
                    background: state.status === "running" ? undefined : style.connector,
                    borderRadius: 2,
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
          const agentUsage = getAgentUsage(run, agent.id);

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
                  width: 3,
                  background: ns.icon,
                  borderRadius: "12px 0 0 12px",
                  opacity: state.status === "pending" ? 0.35 : 0.9,
                }}
              />

              {/* Header button */}
              <button
                type="button"
                className="flex w-full items-start gap-4 pl-6 pr-4 py-4 text-left md:pl-7 md:pr-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--acc)]"
                aria-expanded={open}
                onClick={() => handleSelect(open ? null : agent.id)}
              >
                {/* Agent icon */}
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 10,
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
                  <div className="text-xs font-bold font-mono tracking-wide text-[var(--acc2)]">
                    Agent {agent.number}
                  </div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2">
                    <h3 className="font-bold font-mono text-[var(--text)]">{agent.name}</h3>
                    <StatusBadge status={state.status || "pending"} />
                    {agentUsage?.total_tokens > 0 && (
                      <span
                        className="inline-flex items-center gap-1 rounded-full border border-[rgba(125,211,252,0.3)] bg-[rgba(125,211,252,0.08)] px-2 py-0.5 font-mono text-[10px] font-bold text-[var(--acc)]"
                        title={`${formatTokens(agentUsage.prompt_tokens)} prompt + ${formatTokens(agentUsage.completion_tokens)} completion · ${agentUsage.calls} call${agentUsage.calls > 1 ? "s" : ""}`}
                      >
                        ⚡ {formatTokensCompact(agentUsage.total_tokens)} tokens
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-[var(--mute)]">{agent.description}</p>
                  <p className="mt-1 text-xs font-mono text-[var(--mute)]">
                    {state.started_at ? `Started ${formatTime(state.started_at)}` : "Not started"}
                    {state.finished_at ? ` · Finished ${formatTime(state.finished_at)}` : ""}
                    {agentUsage?.calls > 0 ? ` · ${agentUsage.calls} model call${agentUsage.calls > 1 ? "s" : ""}` : ""}
                  </p>
                </div>

                <ChevronDown
                  size={18}
                  className={`mt-1 shrink-0 text-[var(--acc)] transition ${open ? "rotate-180" : ""}`}
                />
              </button>

              {/* Running message */}
              {state.message && state.status === "running" && (
                <p className="px-5 pb-3 text-xs font-mono text-[var(--acc)]">{state.message}</p>
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
                      <div key={label} className="flex items-center gap-2 rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-3 py-1.5">
                        <span className="text-xs font-semibold font-mono text-[var(--mute)]">{label}</span>
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
                      className="flex items-center justify-between gap-3 rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-3 py-2"
                    >
                      <span className="text-xs font-mono font-medium text-[var(--text)]">{component.name}</span>
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

              {/* Error banner */}
              {state.error && <ErrorBanner error={state.error} className="mx-5 mb-4" />}

              {/* Expandable output panel */}
              <div className={`expand-panel ${open ? "open" : ""}`}>
                <div>
                  <div className="border-t border-[var(--line)] bg-[rgba(10,14,20,0.65)] px-4 py-4 md:px-5">
                    {state.status === "pending" && (
                      <p className="text-xs font-mono text-[var(--mute)]">This agent has not run yet.</p>
                    )}
                    {state.status === "skipped" && (
                      <p className="text-xs font-mono text-[var(--mute)]">
                        This agent did not run because an earlier stage failed.
                      </p>
                    )}
                    {state.status !== "pending" && state.status !== "skipped" && (
                      <>
                        {/* Token usage metrics for this agent */}
                        {agentUsage?.total_tokens > 0 && (
                          <AgentTokenCard usage={agentUsage} />
                        )}

                        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                          {/* View toggle */}
                          <div className="flex rounded-lg border border-[var(--line)] bg-[rgba(36,48,68,0.4)] p-1">
                            {["formatted", "raw"].map((item) => (
                              <button
                                key={item}
                                type="button"
                                onClick={() => setMode(item)}
                                className={`rounded px-3 py-1 text-xs font-semibold font-mono transition ${
                                  mode === item
                                    ? "bg-[var(--line)] text-[var(--acc)] shadow-sm"
                                    : "text-[var(--mute)] hover:text-[var(--text)]"
                                }`}
                              >
                                {item === "formatted" ? "Formatted View" : "Raw JSON View"}
                              </button>
                            ))}
                          </div>
                          {/* Download link */}
                          {runId && (
                            <a
                              href={apiUrl(`/runs/${runId}/download/${agent.file}`)}
                              className="text-xs font-semibold font-mono text-[var(--acc)] hover:text-white"
                            >
                              Download {agent.file}
                            </a>
                          )}
                        </div>

                        {loading && !output && (
                          <p className="flex items-center gap-2 text-xs font-mono text-[var(--mute)]">
                            <Loader2 size={14} className="animate-spin text-[var(--acc)]" />
                            Loading output
                          </p>
                        )}
                        {error && <p className="text-xs font-mono text-[var(--bad)]">{error}</p>}
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
                                ? apiUrl(`/runs/${runId}/download/${agent.file}`)
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
  return <p className="text-xs font-mono text-[var(--mute)]">No formatted view is available for this output.</p>;
}

function RTLStat({ label, value }) {
  return (
    <div className="rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-3 py-2">
      <div className="text-[10px] font-semibold font-mono uppercase tracking-wider text-[var(--mute)]">{label}</div>
      <div className="mt-1 text-lg font-bold font-mono text-[var(--text)]">{value}</div>
    </div>
  );
}

function IssueList({ title, items, warning = false }) {
  const borderColor = warning ? "border-[rgba(251,191,36,0.3)]" : "border-[rgba(248,113,113,0.3)]";
  const background = warning ? "bg-[rgba(251,191,36,0.06)]" : "bg-[rgba(248,113,113,0.06)]";
  const textColor = warning ? "text-[var(--warn)]" : "text-[var(--bad)]";

  return (
    <section className={`rounded-xl border ${borderColor} ${background} p-4`}>
      <h4 className={`mb-2 text-xs font-bold font-mono uppercase tracking-wider ${textColor}`}>{title}</h4>
      {items.length === 0 ? (
        <p className="text-xs font-mono text-[var(--mute)]">None recorded.</p>
      ) : (
        <ul className={`list-disc space-y-1 pl-5 text-xs font-mono ${textColor}`}>
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

function AgentTokenCard({ usage }) {
  if (!usage || !usage.calls) return null;
  const byComponent = Object.entries(usage.by_component || {});
  return (
    <div className="mb-4 rounded-xl border border-[var(--line)] bg-[rgba(10,14,20,0.45)] p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)]/60 pb-2 mb-2.5">
        <span className="flex items-center gap-1.5 font-mono text-xs font-bold uppercase tracking-wider text-[var(--acc)]">
          <span>⚡</span> Agent Token Usage
        </span>
        <span className="font-mono text-[11px] text-[var(--mute)]">
          {usage.calls} model call{usage.calls > 1 ? "s" : ""}{usage.complete ? "" : " (in progress)"}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-2.5 py-2">
          <div className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--mute)]">Total Tokens</div>
          <div className="mt-0.5 font-mono text-sm font-bold text-[var(--text)]">{formatTokens(usage.total_tokens)}</div>
        </div>
        <div className="rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-2.5 py-2">
          <div className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--mute)]">Prompt (Input)</div>
          <div className="mt-0.5 font-mono text-sm font-bold text-[var(--acc2)]">{formatTokens(usage.prompt_tokens)}</div>
        </div>
        <div className="rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-2.5 py-2">
          <div className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--mute)]">Completion (Output)</div>
          <div className="mt-0.5 font-mono text-sm font-bold text-[var(--ok)]">{formatTokens(usage.completion_tokens)}</div>
        </div>
      </div>
      {byComponent.length > 0 && (
        <div className="mt-3 border-t border-[var(--line)]/50 pt-2.5">
          <div className="mb-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">Tokens by Component</div>
          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {byComponent.map(([comp, compUsage]) => (
              <div key={comp} className="flex items-center justify-between rounded-md border border-[var(--line)]/60 bg-[rgba(16,22,32,0.4)] px-2.5 py-1.5 font-mono text-xs">
                <span className="truncate text-[var(--text)] mr-2" title={comp}>{comp}</span>
                <span className="shrink-0 text-[var(--acc)] font-bold">{formatTokensCompact(compUsage.total_tokens)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
