import { useEffect, useState } from "react";
import CodeViewer from "../components/CodeViewer";
import StatusBadge from "../components/StatusBadge";
import { asList, asText } from "../lib/format";

function issueText(issue) {
  if (!issue || typeof issue !== "object" || Array.isArray(issue)) {
    return asText(issue);
  }
  const details = [];
  if (issue.code) details.push(`[${issue.code}]`);
  if (issue.line) details.push(`Line ${issue.line}:`);
  details.push(asText(issue.message, JSON.stringify(issue)));
  return details.join(" ");
}

function IssueList({ title, items, empty = "None recorded." }) {
  return (
    <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
      <h5 className="mb-2 text-sm font-bold text-indigo">{title}</h5>
      {asList(items).length === 0 ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <ul className="list-disc space-y-1 pl-5 text-sm text-[#4A3566]">
          {asList(items).map((item, index) => (
            <li key={`${index}-${issueText(item).slice(0, 32)}`}>{issueText(item)}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Interface({ title, signals }) {
  return (
    <section className="rounded-xl bg-[#F8F5FF] p-3">
      <h5 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">{title}</h5>
      {asList(signals).length === 0 ? (
        <p className="text-sm text-muted">None recorded.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {asList(signals).map((signal, index) => (
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

function PseudocodeComponent({ component, index }) {
  const lines = asList(component.pseudocode).map((line) =>
    typeof line === "string" ? line : JSON.stringify(line),
  );
  const title = component.component_name || component.module_name || `Component ${index + 1}`;
  const filename = `${component.module_name || title}.txt`;

  return (
    <details className="overflow-hidden rounded-2xl border border-[#E9DDFB] bg-white">
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <span>
          <span className="block font-bold text-indigo">{title}</span>
          <span className="mt-0.5 block text-xs text-muted">
            Module: {asText(component.module_name, "Not provided")}
          </span>
        </span>
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={component.generation_status || "not_run"} />
          <StatusBadge status={component.validation_status || "not_run"} />
        </div>
      </summary>
      <div className="grid gap-4 border-t border-[#E9DDFB] bg-[#F8F5FF] p-4">
        <div className="grid gap-3 md:grid-cols-2">
          <Interface title="Inputs" signals={component.inputs} />
          <Interface title="Outputs" signals={component.outputs} />
        </div>
        <CodeViewer lines={lines} title="Generated Pseudocode" downloadName={filename} />
        <IssueList
          title="Validation issues"
          items={component.validation_issues}
          empty="No validation issues recorded."
        />
        <IssueList title="Assumptions" items={component.assumptions} />
        <IssueList
          title="Unresolved requirements"
          items={component.unresolved_issues}
        />
      </div>
    </details>
  );
}

export default function PseudocodeView({ data, runId }) {
  const [rawArtifact, setRawArtifact] = useState("");
  const [hasRaw, setHasRaw] = useState(false);
  const record = data && typeof data === "object" && !Array.isArray(data) ? data : {};
  const components = Array.isArray(record.components)
    ? record.components
    : record.pseudocode
      ? [record]
      : [];

  useEffect(() => {
    let cancelled = false;
    async function loadRaw() {
      if (!runId) return;
      const index = await fetch(`/api/runs/${runId}/outputs`);
      if (!index.ok) return;
      const body = await index.json();
      if (!body.artifacts?.includes("pseudocode_raw.txt")) {
        if (!cancelled) setHasRaw(false);
        return;
      }
      const response = await fetch(`/api/runs/${runId}/download/pseudocode_raw.txt`);
      if (!response.ok || cancelled) return;
      const text = await response.text();
      if (!cancelled) {
        setHasRaw(true);
        setRawArtifact(text.length > 200000 ? `${text.slice(0, 200000)}\n\n[truncated preview]` : text);
      }
    }
    loadRaw().catch(() => setHasRaw(false));
    return () => {
      cancelled = true;
    };
  }, [runId]);

  return (
    <div className="grid gap-4">
      <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h4 className="text-sm font-bold text-indigo">Pseudocode generation summary</h4>
            <p className="mt-1 text-sm text-muted">{components.length} component(s)</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={record.generation_status || "not_run"} />
            <StatusBadge status={record.validation_status || "not_run"} />
          </div>
        </div>
        {record.execution_status && (
          <p className="mt-3 text-sm text-[#4A3566]">
            Execution: <span className="font-semibold">{record.execution_status}</span>
          </p>
        )}
      </section>

      {components.length === 0 ? (
        <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4 text-sm text-muted">
          No component pseudocode was recorded.
        </section>
      ) : (
        <div className="grid gap-3">
          {components.map((component, index) => (
            <PseudocodeComponent
              key={`${component.component_name || component.module_name || "component"}-${index}`}
              component={component}
              index={index}
            />
          ))}
        </div>
      )}

      <IssueList title="Aggregate validation issues" items={record.validation_issues} />
      <IssueList title="Aggregate unresolved requirements" items={record.unresolved_issues} />
      <IssueList title="Execution errors" items={record.execution_errors} />
      {record.execution_output && record.execution_output !== "No execution has been attempted." && (
        <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
          <h4 className="mb-2 text-sm font-bold text-indigo">Execution output</h4>
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs leading-6 text-[#4A3566]">
            {record.execution_output}
          </pre>
        </section>
      )}

      {hasRaw && (
        <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h4 className="text-sm font-bold text-indigo">Raw model response</h4>
            <a href={`/api/runs/${runId}/download/pseudocode_raw.txt`} className="text-xs font-semibold text-[#7540C5]">
              Download pseudocode_raw.txt
            </a>
          </div>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-[#F8F5FF] p-3 font-mono text-xs leading-6 text-[#4A3566]">
            {rawArtifact}
          </pre>
        </section>
      )}
    </div>
  );
}
