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
          <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text)]">Component overview</h4>
          <p className="font-mono text-xs text-[var(--mute)]">{components.length} component(s)</p>
        </div>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search components or signals"
          className="w-full rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.7)] px-3 py-2 font-mono text-xs text-[var(--text)] placeholder-[var(--mute)] outline-none focus:ring-2 focus:ring-[var(--acc)] sm:max-w-xs"
        />
      </div>
      {visible.length === 0 ? (
        <p className="font-mono text-xs text-[var(--mute)]">No components match this search.</p>
      ) : (
        <div className="grid gap-3">
          {visible.map((component, index) => (
            <article key={`${component?.name || "component"}-${index}`} className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4">
              <h5 className="font-mono font-bold text-[var(--acc)]">{asText(component?.name, `Component ${index + 1}`)}</h5>
              <p className="mt-1 font-mono text-xs leading-5 text-[var(--text)]">{asText(component?.purpose)}</p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <div className="mb-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">Inputs</div>
                  <div className="flex flex-wrap gap-1.5">
                    {asList(component?.inputs).length === 0 && <span className="font-mono text-xs text-[var(--mute)]">None.</span>}
                    {asList(component?.inputs).map((signal) => (
                      <span key={signal} className="rounded-md border border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.08)] px-2 py-0.5 font-mono text-[11px] font-medium text-[var(--acc2)]">{asText(signal)}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="mb-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">Outputs</div>
                  <div className="flex flex-wrap gap-1.5">
                    {asList(component?.outputs).length === 0 && <span className="font-mono text-xs text-[var(--mute)]">None.</span>}
                    {asList(component?.outputs).map((signal) => (
                      <span key={signal} className="rounded-md border border-[rgba(125,211,252,0.3)] bg-[rgba(125,211,252,0.08)] px-2 py-0.5 font-mono text-[11px] font-medium text-[var(--acc)]">{asText(signal)}</span>
                    ))}
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      <section className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4">
        <h4 className="mb-1 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">Architecture interactions</h4>
        <p className="mb-3 font-mono text-[11px] text-[var(--mute)]">Connections recorded by the decomposition agent.</p>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {names.map((name, index) => (
            <div key={name} className="flex items-center gap-2">
              <span className="rounded-full border border-[rgba(125,211,252,0.3)] bg-[rgba(125,211,252,0.08)] px-3 py-0.5 font-mono text-xs font-semibold text-[var(--acc)]">{name}</span>
              {index < names.length - 1 && <span className="font-mono text-xs text-[var(--mute)]">→</span>}
            </div>
          ))}
        </div>
        {interactions.length === 0 ? (
          <p className="font-mono text-xs text-[var(--mute)]">No interactions recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left font-mono text-xs">
              <thead className="text-[10px] uppercase tracking-wider text-[var(--mute)]">
                <tr>
                  <th className="px-2 py-2">Source</th>
                  <th className="px-2 py-2">Source signal</th>
                  <th className="px-2 py-2">Destination</th>
                  <th className="px-2 py-2">Destination signal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line)]">
                {interactions.map((item, index) => (
                  <tr key={`${item.raw}-${index}`}>
                    {item.parsed ? (
                      <>
                        <td className="px-2 py-2 font-semibold text-[var(--acc)]">{item.source.component || "—"}</td>
                        <td className="px-2 py-2 text-[var(--mute)]">{item.source.signal || "—"}</td>
                        <td className="px-2 py-2 font-semibold text-[var(--acc)]">{item.destination.component || "—"}</td>
                        <td className="px-2 py-2 text-[var(--mute)]">{item.destination.signal || "—"}</td>
                      </>
                    ) : (
                      <td className="px-2 py-2 text-[var(--text)]" colSpan={4}>{item.raw}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4">
        <h4 className="mb-3 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">Implementation plan</h4>
        {asList(record.implementation_plan).length === 0 ? (
          <p className="font-mono text-xs text-[var(--mute)]">No implementation steps recorded.</p>
        ) : (
          <ol className="space-y-3">
            {asList(record.implementation_plan).map((step, index) => (
              <li key={`${step?.step_number || index}`} className="flex gap-3">
                <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-[rgba(167,139,250,0.4)] bg-[rgba(167,139,250,0.1)] font-mono text-xs font-bold text-[var(--acc2)]">
                  {step?.step_number || index + 1}
                </div>
                <div>
                  <div className="font-mono text-xs font-semibold text-[var(--text)]">{asText(step?.title, `Step ${index + 1}`)}</div>
                  <p className="mt-0.5 font-mono text-xs leading-5 text-[var(--mute)]">{asText(step?.description, "")}</p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
