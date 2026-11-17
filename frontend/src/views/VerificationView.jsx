import { useState } from "react";
import { asList, asText } from "../lib/format";

export default function VerificationView({ data, components = [], descriptions = [] }) {
  const [query, setQuery] = useState("");
  const results = Array.isArray(data) ? data : data ? [data] : [];
  const rows = results.map((result, index) => ({
    result,
    name: components[index]?.name || descriptions[index]?.module_name || `Component ${index + 1}`,
  }));
  const passed = rows.filter((row) => row.result?.valid === true).length;
  const failed = rows.filter((row) => row.result?.valid === false).length;
  const unknown = rows.length - passed - failed;
  const needle = query.trim().toLowerCase();
  const visible = rows.filter((row) => {
    if (!needle) return true;
    const issues = asList(row.result?.issues).join(" ");
    const suggestions = asList(row.result?.suggestions).join(" ");
    return `${row.name} ${issues} ${suggestions} ${row.result?.reasoning || ""}`.toLowerCase().includes(needle);
  });

  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          ["Verified", rows.length, "text-[var(--text)]"],
          ["Passed", passed, "text-[var(--ok)]"],
          ["Failed", failed, "text-[var(--bad)]"],
          ["Unspecified", unknown, "text-[var(--mute)]"],
        ].map(([label, value, color]) => (
          <div key={label} className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-4 py-3">
            <div className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--mute)]">{label}</div>
            <div className={`mt-1 font-mono text-2xl font-bold ${color}`}>{value}</div>
          </div>
        ))}
      </div>
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search components, issues, or suggestions"
        className="w-full rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.7)] px-3 py-2 font-mono text-xs text-[var(--text)] placeholder-[var(--mute)] outline-none focus:ring-2 focus:ring-[var(--acc)] sm:max-w-md"
      />
      {visible.length === 0 && <p className="font-mono text-xs text-[var(--mute)]">No verification results match this search.</p>}
      {visible.map((row, index) => {
        const valid = row.result?.valid;
        const tone =
          valid === true
            ? "border-[rgba(74,222,128,0.35)] bg-[rgba(74,222,128,0.07)]"
            : valid === false
              ? "border-[rgba(248,113,113,0.35)] bg-[rgba(248,113,113,0.07)]"
              : "border-[var(--line)] bg-[rgba(16,22,32,0.6)]";
        return (
          <article key={`${row.name}-${index}`} className={`rounded-xl border p-4 ${tone}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="font-mono font-bold text-[var(--acc)]">{row.name}</h4>
              <span
                className={`rounded-full px-2.5 py-1 font-mono text-[11px] font-bold ${
                  valid === true
                    ? "bg-[rgba(74,222,128,0.15)] text-[var(--ok)]"
                    : valid === false
                      ? "bg-[rgba(248,113,113,0.15)] text-[var(--bad)]"
                      : "bg-[rgba(125,138,163,0.1)] text-[var(--mute)]"
                }`}
              >
                {valid === true ? "Valid" : valid === false ? "Invalid" : "Unspecified"}
              </span>
            </div>
            <div className="mt-3 grid gap-3">
              <div>
                <h5 className="mb-1 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--bad)]">Issues</h5>
                {asList(row.result?.issues).length === 0 ? (
                  <p className="font-mono text-xs text-[var(--mute)]">No issues recorded.</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-5 font-mono text-xs text-[var(--bad)]">
                    {asList(row.result.issues).map((issue, issueIndex) => (
                      <li key={issueIndex}>{asText(issue)}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h5 className="mb-1 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--warn)]">Suggestions</h5>
                {asList(row.result?.suggestions).length === 0 ? (
                  <p className="font-mono text-xs text-[var(--mute)]">No suggestions recorded.</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-5 font-mono text-xs text-[var(--warn)]">
                    {asList(row.result.suggestions).map((item, itemIndex) => (
                      <li key={itemIndex}>{asText(item)}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h5 className="mb-1 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">Reasoning</h5>
                <p className="font-mono text-xs leading-5 text-[var(--text)]">{asText(row.result?.reasoning)}</p>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
