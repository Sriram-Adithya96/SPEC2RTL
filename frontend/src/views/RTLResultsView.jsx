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
        background: "#1E0B38",
        border: "1px solid rgba(197,166,242,0.18)",
        borderRadius: 16,
        overflow: "hidden",
      }}
    >
      <div
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
        style={{
          background: "rgba(255,255,255,0.05)",
          borderBottom: "1px solid rgba(197,166,242,0.12)",
        }}
      >
        <h4 className="text-sm font-bold" style={{ color: "#C5A6F2" }}>{title}</h4>
        {source.trim() && (
          <button
            type="button"
            onClick={copy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#C5A6F2]/30 px-2.5 py-1.5 text-xs font-semibold text-[#C5A6F2] hover:bg-white/10 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5]"
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
                <tr key={`${index}-${line}`} className="align-top">
                  <td
                    style={{
                      color: "#6B4E9E",
                      userSelect: "none",
                      paddingLeft: 12,
                      paddingRight: 12,
                      textAlign: "right",
                      width: 44,
                    }}
                  >
                    {index + 1}
                  </td>
                  <td
                    style={{
                      color: "#E9DEFF",
                      paddingLeft: 12,
                      paddingRight: 12,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {line || " "}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="px-4 py-6 text-sm" style={{ color: "#A879E5" }}>{emptyMessage}</p>
      )}
      {copyError && <p className="border-t border-[#F3C0C0] bg-[#FFF6F6] px-4 py-2 text-sm text-[#8F1D1D]">{copyError}</p>}
    </section>
  );
}

function SignalList({ title, signals }) {
  const items = asList(signals);
  return (
    <section className="rounded-xl bg-[#F8F5FF] p-3">
      <h5 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">{title}</h5>
      {items.length === 0 ? (
        <p className="text-sm text-muted">None recorded.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {items.map((signal, index) => (
            <span
              key={`${index}-${String(signal)}`}
              className="rounded-lg bg-[#E9DDFB] px-2 py-1 text-xs font-medium text-[#4A3566]"
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
      ? "border-[#F3C0C0] bg-[#FFF6F6] text-[#8F1D1D]"
      : tone === "warning"
        ? "border-[#E7D7A1] bg-[#FFF8EA] text-[#7A5B12]"
        : "border-[#E9DDFB] bg-white text-[#4A3566]";

  return (
    <section className={`rounded-2xl border ${palette} p-4`}>
      <h4 className="mb-2 text-sm font-bold">{title}</h4>
      {values.length === 0 ? (
        <p className="text-sm text-muted">{emptyMessage}</p>
      ) : (
        <ul className="list-disc space-y-1 pl-5 text-sm">
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
    <section className="grid gap-4 rounded-3xl border border-white/80 bg-white/80 p-4 shadow-card backdrop-blur md:p-5">
      <div>
        <h3 className="text-lg font-bold text-indigo">Component RTL Explorer</h3>
        <p className="mt-1 text-sm text-muted">
          Browse component modules recorded in this run's RTL artifact.
        </p>
      </div>

      {modules.length === 0 ? (
        <p className="rounded-2xl border border-[#E9DDFB] bg-[#F8F5FF] p-4 text-sm text-muted">
          No component module records were returned.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(12rem,0.32fr)_minmax(0,1fr)]">
          <nav aria-label="RTL component modules" className="grid content-start gap-2">
            {modules.map((module, index) => {
              const label =
                module?.component_name ||
                module?.module_name ||
                `Component ${index + 1}`;
              return (
                <button
                  type="button"
                  key={`${label}-${index}`}
                  aria-pressed={activeIndex === index}
                  onClick={() => setSelectedIndex(index)}
                  className={`flex items-center justify-between gap-2 rounded-xl border px-3 py-2 text-left text-sm font-semibold transition ${
                    activeIndex === index
                      ? "border-[#7540C5] bg-[#E9DDFB] text-indigo"
                      : "border-[#E9DDFB] bg-white text-[#4A3566] hover:bg-[#F8F5FF]"
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
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#E9DDFB] bg-white p-4">
                <div>
                  <h4 className="font-bold text-indigo">
                    {asText(selected.module_name, "Unnamed module")}
                  </h4>
                  <p className="mt-1 text-xs text-muted">
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
                <StringList
                  title="Component generation error"
                  items={[selected.generation_error]}
                  tone="error"
                />
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
    <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
      <h4 className="mb-3 text-sm font-bold text-indigo">Component instances and connections</h4>
      {values.length === 0 ? (
        <p className="text-sm text-muted">No integrated component instances were recorded.</p>
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
                className="rounded-xl bg-[#F8F5FF] p-3"
              >
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
                  <span className="font-bold text-indigo">
                    {asText(instance?.module_name, "Unnamed module")}
                  </span>
                  <span className="text-muted">
                    instance {asText(instance?.instance_name, `#${index + 1}`)}
                  </span>
                </div>
                {connections.length === 0 ? (
                  <p className="mt-2 text-xs text-muted">No port connections recorded.</p>
                ) : (
                  <dl className="mt-2 grid gap-1 sm:grid-cols-2">
                    {connections.map(([port, signal]) => (
                      <div key={port} className="break-all text-xs text-[#4A3566]">
                        <dt className="inline font-semibold">{port}</dt>
                        <dd className="inline"> ← {asText(signal)}</dd>
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
  const validatedCount = modules.filter(
    (module) => (
      module?.interface_validation_status
        ? normalizedStatus(module.interface_validation_status) === "passed"
        : normalizedStatus(module?.generation_status) === "completed"
    ),
  ).length;
  const generationIssues = asList(result.generation_issues);
  const unresolvedIssues = asList(result.unresolved_issues);
  const assumptions = asList(result.assumptions);

  return (
    <div className="grid gap-5">
      <section className="rounded-3xl border border-white/80 bg-white/80 p-5 shadow-card backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-[#A879E5]">
              {result.experimental ? "Experimental RTL — Not Production Verified" : "RTL Generation"}
            </p>
            <h3 className="mt-1 text-lg font-bold text-indigo">RTL Generation Results</h3>
            {result.module_name && (
              <p className="mt-1 text-sm text-muted">
                Top-level module: {result.module_name}
              </p>
            )}
            {result.language && (
              <p className="mt-1 text-xs text-muted">Language: {result.language}</p>
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

      <section className="grid gap-4 rounded-3xl border border-white/80 bg-white/80 p-4 shadow-card backdrop-blur md:p-5">
        <div>
          <h3 className="text-lg font-bold text-indigo">Integrated Top-Level RTL</h3>
          <p className="mt-1 text-sm text-muted">
            Integrated top-level wiring is available only when integration succeeds.
          </p>
          {runId && (
            <div className="mt-3 flex flex-wrap gap-2">
              <a
                href={`/api/runs/${runId}/download/integrated_rtl.v`}
                className="inline-flex items-center gap-1.5 rounded-xl border border-[#E9DDFB] bg-white px-3 py-1.5 text-xs font-semibold text-[#7540C5] hover:bg-[#F8F5FF]"
              >
                ↓ integrated_rtl.v
              </a>
              <a
                href={`/api/runs/${runId}/download/top_level_rtl.v`}
                className="inline-flex items-center gap-1.5 rounded-xl border border-[#E9DDFB] bg-white px-3 py-1.5 text-xs font-semibold text-[#7540C5] hover:bg-[#F8F5FF]"
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
        <StringList
          title="Generation issues"
          items={generationIssues}
          emptyMessage="No generation issues were recorded."
          tone="error"
        />
        <StringList
          title="Unresolved issues"
          items={unresolvedIssues}
          emptyMessage="No unresolved issues were recorded."
          tone="warning"
        />
      </div>
      <StringList
        title="Assumptions"
        items={assumptions}
        emptyMessage="No assumptions were recorded."
      />
    </div>
  );
}

function OverviewStat({ label, value }) {
  return (
    <div className="rounded-2xl bg-[#F8F5FF] px-4 py-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 text-xl font-bold text-indigo">{value}</div>
    </div>
  );
}

function StageStatus({ label, status, fallback }) {
  const value = status || fallback;
  if (!value) return null;
  return (
    <div className="flex items-center gap-2 rounded-xl bg-[#F8F5FF] px-3 py-2">
      <span className="text-xs font-semibold text-muted">{label}</span>
      <StatusBadge status={normalizedStatus(value)} />
    </div>
  );
}
