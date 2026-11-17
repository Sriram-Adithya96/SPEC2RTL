import { Check, Copy } from "lucide-react";
import { useState } from "react";
import StatusBadge from "../components/StatusBadge";
import { asList, asText } from "../lib/format";

function normalizedStatus(status) {
  return typeof status === "string" && status.trim()
    ? status.trim().toLowerCase().replaceAll(" ", "_")
    : "not_run";
}

function RTLCode({ code, title, emptyMessage }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const source = typeof code === "string" ? code : "";
  const lines = source.split("\n");

  async function copy() {
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      setCopyError("");
      setTimeout(() => setCopied(false), 1600);
    } catch (error) {
      setCopied(false);
      setCopyError(error?.message || "Could not copy RTL to the clipboard.");
    }
  }

  return (
    <section
      style={{
        background: "#05080d",
        border: "1px solid var(--line, #243044)",
        borderRadius: 12,
        overflow: "hidden",
      }}
    >
      <div
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
        style={{ background: "rgba(16,22,32,0.85)", borderBottom: "1px solid var(--line, #243044)" }}
      >
        <h4 className="font-mono text-sm font-bold" style={{ color: "var(--text, #d6deeb)" }}>{title}</h4>
        {source.trim() && (
          <button
            type="button"
            onClick={copy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--line)] bg-transparent px-2.5 py-1.5 font-mono text-xs font-semibold text-[var(--mute)] hover:text-[var(--text)] hover:border-[var(--acc)] hover:bg-[rgba(125,211,252,0.08)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)]"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </div>
      {source.trim() ? (
        <div className="max-h-[34rem] overflow-auto">
          <table
            className="w-full border-collapse text-xs leading-6"
            style={{ fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace" }}
          >
            <tbody>
              {lines.map((line, index) => (
                <tr key={`${index}-${line}`} className="align-top hover:bg-[rgba(125,211,252,0.02)]">
                  <td style={{ color: "var(--mute, #7d8aa3)", opacity: 0.6, userSelect: "none", paddingLeft: 12, paddingRight: 12, textAlign: "right", width: 44, borderRight: "1px solid rgba(36,48,68,0.5)" }}>
                    {index + 1}
                  </td>
                  <td style={{ color: "#9fb3d1", paddingLeft: 12, paddingRight: 12, whiteSpace: "pre-wrap" }}>
                    {line || " "}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="px-4 py-6 font-mono text-xs" style={{ color: "var(--mute, #7d8aa3)" }}>{emptyMessage}</p>
      )}
      {copyError && (
        <p className="border-t border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.08)] px-4 py-2 font-mono text-xs text-[var(--bad)]">{copyError}</p>
      )}
    </section>
  );
}

function SignalList({ title, signals }) {
  const items = asList(signals);
  return (
    <section className="rounded-lg border border-[var(--line)] bg-[rgba(10,14,20,0.4)] p-3">
      <h5 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">{title}</h5>
      {items.length === 0 ? (
        <p className="font-mono text-xs text-[var(--mute)]">None recorded.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {items.map((signal, index) => (
            <span
              key={`${index}-${String(signal)}`}
              className="rounded-md border border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.08)] px-2 py-0.5 font-mono text-[11px] font-medium text-[var(--acc2)]"
            >
              {asText(signal)}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

function StringList({ title, items, emptyMessage = "None recorded.", tone = "default" }) {
  const values = asList(items);
  const palette =
    tone === "error"
      ? "border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.07)] text-[var(--bad)]"
      : tone === "warning"
        ? "border-[rgba(251,191,36,0.3)] bg-[rgba(251,191,36,0.07)] text-[var(--warn)]"
        : "border-[var(--line)] bg-[rgba(16,22,32,0.6)] text-[var(--text)]";

  return (
    <section className={`rounded-xl border ${palette} p-4`}>
      <h4 className="mb-2 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">{title}</h4>
      {values.length === 0 ? (
        <p className="font-mono text-xs text-[var(--mute)]">{emptyMessage}</p>
      ) : (
        <ul className="list-disc space-y-1 pl-5 font-mono text-xs">
          {values.map((item, index) => (
            <li key={`${index}-${String(item)}`}>
              {typeof item === "string" ? item : JSON.stringify(item)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ComponentExplorer({ modules }) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const activeIndex = Math.min(selectedIndex, modules.length - 1);
  const selected = modules[activeIndex] || null;

  return (
    <section className="grid gap-4 rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4 md:p-5">
      <div>
        <h3 className="font-mono text-sm font-bold text-[var(--text)]">Component RTL Explorer</h3>
        <p className="mt-1 font-mono text-xs text-[var(--mute)]">
          Browse component modules recorded in this run's RTL artifact.
        </p>
      </div>

      {modules.length === 0 ? (
        <p className="rounded-xl border border-[var(--line)] bg-[rgba(10,14,20,0.4)] p-4 font-mono text-xs text-[var(--mute)]">
          No component module records were returned.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(12rem,0.32fr)_minmax(0,1fr)]">
          <nav aria-label="RTL component modules" className="grid content-start gap-2">
            {modules.map((module, index) => {
              const label = module?.component_name || module?.module_name || `Component ${index + 1}`;
              return (
                <button
                  type="button"
                  key={`${label}-${index}`}
                  aria-pressed={activeIndex === index}
                  onClick={() => setSelectedIndex(index)}
                  className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left font-mono text-xs font-semibold transition ${
                    activeIndex === index
                      ? "border-[var(--acc2)] bg-[rgba(167,139,250,0.14)] text-[var(--text)]"
                      : "border-[var(--line)] bg-transparent text-[var(--mute)] hover:text-[var(--text)] hover:bg-[rgba(36,48,68,0.4)]"
                  }`}
                >
                  <span className="break-all">{label}</span>
                  <StatusBadge status={normalizedStatus(module?.interface_validation_status || module?.generation_status)} />
                </button>
              );
            })}
          </nav>

          {selected && (
            <div className="grid min-w-0 content-start gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4">
                <div>
                  <h4 className="font-mono font-bold text-[var(--acc)]">
                    {asText(selected.module_name, "Unnamed module")}
                  </h4>
                  <p className="mt-1 font-mono text-xs text-[var(--mute)]">
                    Component: {asText(selected.component_name, "Not provided")}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge status={normalizedStatus(selected.generation_status)} />
                  {selected.interface_validation_status && (
                    <StatusBadge status={normalizedStatus(selected.interface_validation_status)} />
                  )}
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <SignalList title="Inputs" signals={selected.inputs} />
                <SignalList title="Outputs" signals={selected.outputs} />
              </div>

              {selected.generation_error && (
                <StringList title="Component generation error" items={[selected.generation_error]} tone="error" />
              )}
              <RTLCode
                code={selected.rtl_code}
                title="Component Verilog RTL"
                emptyMessage="No RTL source was generated for this component."
              />
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function IntegratedInstances({ instances }) {
  const values = asList(instances);
  return (
    <section className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4">
      <h4 className="mb-3 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">Component instances and connections</h4>
      {values.length === 0 ? (
        <p className="font-mono text-xs text-[var(--mute)]">No integrated component instances were recorded.</p>
      ) : (
        <div className="grid gap-3">
          {values.map((instance, index) => {
            const connections =
              instance?.port_connections &&
              typeof instance.port_connections === "object" &&
              !Array.isArray(instance.port_connections)
                ? Object.entries(instance.port_connections)
                : [];
            return (
              <article
                key={`${instance?.instance_name || instance?.component_name || "instance"}-${index}`}
                className="rounded-lg border border-[var(--line)] bg-[rgba(10,14,20,0.4)] p-3"
              >
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-xs">
                  <span className="font-bold text-[var(--acc)]">
                    {asText(instance?.module_name, "Unnamed module")}
                  </span>
                  <span className="text-[var(--mute)]">
                    instance {asText(instance?.instance_name, `#${index + 1}`)}
                  </span>
                </div>
                {connections.length === 0 ? (
                  <p className="mt-2 font-mono text-xs text-[var(--mute)]">No port connections recorded.</p>
                ) : (
                  <dl className="mt-2 grid gap-1 font-mono text-xs sm:grid-cols-2">
                    {connections.map(([port, signal]) => (
                      <div key={port} className="break-all text-[var(--text)]">
                        <dt className="inline font-semibold text-[var(--acc2)]">{port}</dt>
                        <dd className="inline text-[var(--mute)]"> ← {asText(signal)}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default function RTLResultsView({ data, runId }) {
  const result = data && typeof data === "object" && !Array.isArray(data) ? data : {};
  const modules = Array.isArray(result.component_modules) ? result.component_modules : [];
  const generatedCount = modules.filter(
    (module) => typeof module?.rtl_code === "string" && module.rtl_code.trim().length > 0,
  ).length;
  const validatedCount = modules.filter((module) =>
    module?.interface_validation_status
      ? normalizedStatus(module.interface_validation_status) === "passed"
      : normalizedStatus(module?.generation_status) === "completed",
  ).length;
  const generationIssues = asList(result.generation_issues);
  const unresolvedIssues = asList(result.unresolved_issues);
  const assumptions = asList(result.assumptions);

  return (
    <div className="grid gap-5">
      <section className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--acc2)]">
              {result.experimental ? "Experimental RTL — Not Production Verified" : "RTL Generation"}
            </p>
            <h3 className="mt-1 font-mono text-sm font-bold text-[var(--text)]">RTL Generation Results</h3>
            {result.module_name && (
              <p className="mt-1 font-mono text-xs text-[var(--mute)]">Top-level module: {result.module_name}</p>
            )}
            {result.language && (
              <p className="mt-1 font-mono text-xs text-[var(--mute)]">Language: {result.language}</p>
            )}
          </div>
          <StatusBadge status={normalizedStatus(result.generation_status)} />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <OverviewStat label="Component records" value={modules.length} />
          <OverviewStat label="Modules with RTL" value={generatedCount} />
          <OverviewStat label="Interfaces passed" value={validatedCount} />
          <OverviewStat label="Generation issues" value={generationIssues.length} />
          <OverviewStat label="Unresolved issues" value={unresolvedIssues.length} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <StageStatus label="Component generation" status={result.component_generation_status} fallback={result.generation_status} />
          <StageStatus label="Interface validation" status={result.interface_validation_status} />
          <StageStatus label="Integration" status={result.integration_status} />
          <StageStatus label="RTL agent" status={result.rtl_agent_status} fallback={result.generation_status} />
        </div>
      </section>

      <ComponentExplorer modules={modules} />

      <section className="grid gap-4 rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4 md:p-5">
        <div>
          <h3 className="font-mono text-sm font-bold text-[var(--text)]">Integrated Top-Level RTL</h3>
          <p className="mt-1 font-mono text-xs text-[var(--mute)]">
            Integrated top-level wiring is available only when integration succeeds.
          </p>
          {runId && (
            <div className="mt-3 flex flex-wrap gap-2">
              <a
                href={`/api/runs/${runId}/download/integrated_rtl.v`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--line)] bg-transparent px-3 py-1.5 font-mono text-xs font-semibold text-[var(--acc)] hover:border-[var(--acc)] hover:bg-[rgba(125,211,252,0.06)] transition"
              >
                ↓ integrated_rtl.v
              </a>
              <a
                href={`/api/runs/${runId}/download/top_level_rtl.v`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--line)] bg-transparent px-3 py-1.5 font-mono text-xs font-semibold text-[var(--acc)] hover:border-[var(--acc)] hover:bg-[rgba(125,211,252,0.06)] transition"
              >
                ↓ top_level_rtl.v
              </a>
            </div>
          )}
        </div>
        <RTLCode
          code={result.rtl_code}
          title={result.module_name ? `${result.module_name} Verilog RTL` : "Top-level Verilog RTL"}
          emptyMessage="Top-level RTL is not available in this run's artifact."
        />
        <IntegratedInstances instances={result.component_instances} />
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <StringList title="Generation issues" items={generationIssues} emptyMessage="No generation issues were recorded." tone="error" />
        <StringList title="Unresolved issues" items={unresolvedIssues} emptyMessage="No unresolved issues were recorded." tone="warning" />
      </div>
      <StringList title="Assumptions" items={assumptions} emptyMessage="No assumptions were recorded." />
    </div>
  );
}

function OverviewStat({ label, value }) {
  return (
    <div className="rounded-lg border border-[var(--line)] bg-[rgba(10,14,20,0.4)] px-4 py-3">
      <div className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--mute)]">{label}</div>
      <div className="mt-1 font-mono text-xl font-bold text-[var(--text)]">{value}</div>
    </div>
  );
}

function StageStatus({ label, status, fallback }) {
  const value = status || fallback;
  if (!value) return null;
  return (
    <div className="flex items-center gap-2 rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-3 py-2">
      <span className="font-mono text-xs font-semibold text-[var(--mute)]">{label}</span>
      <StatusBadge status={normalizedStatus(value)} />
    </div>
  );
}
