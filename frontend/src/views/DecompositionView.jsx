import { useMemo, useState } from "react";
import { asList, asText } from "../lib/format";

function endpoint(fragment, names) {
  const text = String(fragment || "").trim();
  const ordered = [...names].sort((a, b) => b.length - a.length);
  for (const name of ordered) {
    if (text === name) return { component: name, signal: "" };
    if (text.startsWith(`${name} `)) {
      return { component: name, signal: text.slice(name.length).trim() };
    }
  }
  return { component: "", signal: text };
}

export default function DecompositionView({ data }) {
  const [query, setQuery] = useState("");
  const record = data && typeof data === "object" && !Array.isArray(data) ? data : {};
  const components = asList(record.components);
  const names = components.map((item) => item?.name).filter(Boolean);
  const needle = query.trim().toLowerCase();

  const visible = components.filter((component) => {
    if (!needle) return true;
    const haystack = [
      component?.name,
      component?.purpose,
      ...asList(component?.inputs),
      ...asList(component?.outputs),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });

  const interactions = useMemo(
    () =>
      asList(record.interactions).map((item) => {
        const text = asText(item, "");
        const parts = text.split(/\s+->\s+/);
        if (parts.length !== 2) return { raw: text, parsed: false };
        return {
          raw: text,
          parsed: true,
          source: endpoint(parts[0], names),
          destination: endpoint(parts[1], names),
        };
      }),
    [record.interactions, names.join("|")],
  );

  return (
    <div className="grid gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h4 className="text-sm font-bold text-indigo">Component overview</h4>
          <p className="text-sm text-muted">{components.length} component(s)</p>
        </div>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search components or signals"
          className="w-full rounded-xl border border-[#E9DDFB] bg-white px-3 py-2 text-sm outline-none ring-[#7540C5] focus:ring-2 sm:max-w-xs"
        />
      </div>
      {visible.length === 0 ? (
        <p className="text-sm text-muted">No components match this search.</p>
      ) : (
        <div className="grid gap-3">
          {visible.map((component, index) => (
            <article key={`${component?.name || "component"}-${index}`} className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
              <h5 className="font-bold text-indigo">{asText(component?.name, `Component ${index + 1}`)}</h5>
              <p className="mt-1 text-sm leading-6 text-[#4A3566]">{asText(component?.purpose)}</p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <div className="mb-1 text-xs font-bold uppercase tracking-wide text-muted">Inputs</div>
                  <div className="flex flex-wrap gap-1.5">
                    {asList(component?.inputs).length === 0 && <span className="text-sm text-muted">None recorded.</span>}
                    {asList(component?.inputs).map((signal) => (
                      <span key={signal} className="rounded-lg bg-[#E9DDFB] px-2 py-1 text-xs font-medium text-[#4A3566]">{asText(signal)}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-xs font-bold uppercase tracking-wide text-muted">Outputs</div>
                  <div className="flex flex-wrap gap-1.5">
                    {asList(component?.outputs).length === 0 && <span className="text-sm text-muted">None recorded.</span>}
                    {asList(component?.outputs).map((signal) => (
                      <span key={signal} className="rounded-lg bg-[#F8F5FF] px-2 py-1 text-xs font-medium text-[#4A3566]">{asText(signal)}</span>
                    ))}
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
        <h4 className="mb-1 text-sm font-bold text-indigo">Architecture interactions</h4>
        <p className="mb-3 text-xs text-muted">Connections are shown only where the decomposition recorded them.</p>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {names.map((name, index) => (
            <div key={name} className="flex items-center gap-2">
              <span className="rounded-full bg-[#E9DDFB] px-3 py-1 text-xs font-semibold text-[#7540C5]">{name}</span>
              {index < names.length - 1 && <span className="text-[#A879E5]">→</span>}
            </div>
          ))}
        </div>
        {interactions.length === 0 ? (
          <p className="text-sm text-muted">No interactions recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-2 py-2">Source</th>
                  <th className="px-2 py-2">Source signal</th>
                  <th className="px-2 py-2">Destination</th>
                  <th className="px-2 py-2">Destination signal</th>
                </tr>
              </thead>
              <tbody>
                {interactions.map((item, index) => (
                  <tr key={`${item.raw}-${index}`} className="border-t border-[#E9DDFB]">
                    {item.parsed ? (
                      <>
                        <td className="px-2 py-2 font-medium">{item.source.component || "—"}</td>
                        <td className="px-2 py-2">{item.source.signal || "—"}</td>
                        <td className="px-2 py-2 font-medium">{item.destination.component || "—"}</td>
                        <td className="px-2 py-2">{item.destination.signal || "—"}</td>
                      </>
                    ) : (
                      <td className="px-2 py-2 text-[#4A3566]" colSpan={4}>{item.raw}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
        <h4 className="mb-3 text-sm font-bold text-indigo">Implementation plan</h4>
        {asList(record.implementation_plan).length === 0 ? (
          <p className="text-sm text-muted">No implementation steps recorded.</p>
        ) : (
          <ol className="space-y-3">
            {asList(record.implementation_plan).map((step, index) => (
              <li key={`${step?.step_number || index}`} className="flex gap-3">
                <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[#E9DDFB] text-xs font-bold text-[#7540C5]">
                  {step?.step_number || index + 1}
                </div>
                <div>
                  <div className="text-sm font-semibold text-indigo">{asText(step?.title, `Step ${index + 1}`)}</div>
                  <p className="text-sm leading-6 text-[#4A3566]">{asText(step?.description, "")}</p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
