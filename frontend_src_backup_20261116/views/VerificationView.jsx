import { useState } from "react";
import { asList, asText } from "../lib/format";

export default function VerificationView({ data, components = [], descriptions = [] }) {
  const [query, setQuery] = useState("");
  const results = Array.isArray(data) ? data : data ? [data] : [];
  const rows = results.map((result, index) => ({
    result,
    name:
      components[index]?.name ||
      descriptions[index]?.module_name ||
      `Component ${index + 1}`,
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
          ["Verified", rows.length],
          ["Passed", passed],
          ["Failed", failed],
          ["Unspecified", unknown],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl border border-[#E9DDFB] bg-white px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
            <div className="mt-1 text-2xl font-bold text-indigo">{value}</div>
          </div>
        ))}
      </div>
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search components, issues, or suggestions"
        className="w-full rounded-xl border border-[#E9DDFB] bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#7540C5] sm:max-w-md"
      />
      {visible.length === 0 && <p className="text-sm text-muted">No verification results match this search.</p>}
      {visible.map((row, index) => {
        const valid = row.result?.valid;
        const tone = valid === true ? "border-[#C8F52F] bg-[#F8FDE8]" : valid === false ? "border-[#F3C0C0] bg-[#FFF6F6]" : "border-[#E9DDFB] bg-white";
        return (
          <article key={`${row.name}-${index}`} className={`rounded-2xl border p-4 ${tone}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="font-bold text-indigo">{row.name}</h4>
              <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${valid === true ? "bg-[#C8F52F] text-[#35145D]" : valid === false ? "bg-[#FDECEC] text-[#B42318]" : "bg-[#E9DDFB] text-muted"}`}>
                {valid === true ? "Valid" : valid === false ? "Invalid" : "Unspecified"}
              </span>
            </div>
            <div className="mt-3 grid gap-3">
              <div>
                <h5 className="mb-1 text-xs font-bold uppercase tracking-wide text-[#B42318]">Issues</h5>
                {asList(row.result?.issues).length === 0 ? (
                  <p className="text-sm text-muted">No issues recorded.</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-[#8F1D1D]">
                    {asList(row.result.issues).map((issue, issueIndex) => (
                      <li key={issueIndex}>{asText(issue)}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h5 className="mb-1 text-xs font-bold uppercase tracking-wide text-[#9A6700]">Suggestions</h5>
                {asList(row.result?.suggestions).length === 0 ? (
                  <p className="text-sm text-muted">No suggestions recorded.</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-[#7A5B12]">
                    {asList(row.result.suggestions).map((item, itemIndex) => (
                      <li key={itemIndex}>{asText(item)}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h5 className="mb-1 text-xs font-bold uppercase tracking-wide text-muted">Reasoning</h5>
                <p className="text-sm leading-6 text-[#4A3566]">{asText(row.result?.reasoning)}</p>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
