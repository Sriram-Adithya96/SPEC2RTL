import { ChevronDown } from "lucide-react";
import { useState } from "react";
import SignalTable from "../components/SignalTable";
import { asList, asText } from "../lib/format";

export default function DescriptionView({ data }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(0);
  const descriptions = Array.isArray(data) ? data : data ? [data] : [];
  const needle = query.trim().toLowerCase();
  const visible = descriptions.filter((item) => {
    if (!needle) return true;
    const signals = [...asList(item?.inputs), ...asList(item?.outputs), ...asList(item?.state_elements)];
    const haystack = [item?.module_name, item?.purpose, ...signals.map((signal) => signal?.name)]
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });

  return (
    <div className="grid gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="font-mono text-xs text-[var(--mute)]">{descriptions.length} component description(s)</p>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search components or signals"
          className="w-full rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.7)] px-3 py-2 font-mono text-xs text-[var(--text)] placeholder-[var(--mute)] outline-none focus:ring-2 focus:ring-[var(--acc)] sm:max-w-xs"
        />
      </div>
      {visible.length === 0 && <p className="font-mono text-xs text-[var(--mute)]">No descriptions match this search.</p>}
      {visible.map((item, index) => {
        const expanded = open === index;
        return (
          <article key={`${item?.module_name || "module"}-${index}`} className="overflow-hidden rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)]">
            <button
              className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-[rgba(125,211,252,0.03)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--acc)]"
              onClick={() => setOpen(expanded ? -1 : index)}
            >
              <span>
                <span className="block font-mono font-bold text-[var(--acc)]">{asText(item?.module_name, `Component ${index + 1}`)}</span>
                <span className="block font-mono text-xs text-[var(--mute)]">{asText(item?.purpose, "")}</span>
              </span>
              <ChevronDown size={16} className={`shrink-0 text-[var(--acc)] transition ${expanded ? "rotate-180" : ""}`} />
            </button>
            {expanded && (
              <div className="grid gap-4 border-t border-[var(--line)] px-4 py-4">
                <div>
                  <h5 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">Inputs</h5>
                  <SignalTable signals={item?.inputs} />
                </div>
                <div>
                  <h5 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">Outputs</h5>
                  <SignalTable signals={item?.outputs} />
                </div>
                <div>
                  <h5 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">State elements</h5>
                  {asList(item?.state_elements).length === 0 ? (
                    <p className="font-mono text-xs text-[var(--mute)]">No state elements recorded.</p>
                  ) : (
                    <div className="overflow-x-auto rounded-xl border border-[var(--line)] bg-[rgba(10,14,20,0.4)]">
                      <table className="min-w-full text-left font-mono text-xs">
                        <thead className="bg-[rgba(16,22,32,0.85)] text-[10px] uppercase tracking-wider text-[var(--mute)]">
                          <tr>
                            <th className="px-3 py-2.5">Name</th>
                            <th className="px-3 py-2.5">Type</th>
                            <th className="px-3 py-2.5">Width</th>
                            <th className="px-3 py-2.5">Reset</th>
                            <th className="px-3 py-2.5">Description</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--line)]">
                          {asList(item.state_elements).map((element, elementIndex) => (
                            <tr key={`${element?.name}-${elementIndex}`}>
                              <td className="px-3 py-2 font-semibold text-[var(--acc)]">{asText(element?.name, "—")}</td>
                              <td className="px-3 py-2 text-[var(--text)]">{asText(element?.type, "—")}</td>
                              <td className="px-3 py-2 text-[var(--text)]">{asText(element?.width, "—")}</td>
                              <td className="px-3 py-2 text-[var(--mute)]">{asText(element?.reset_value, "—")}</td>
                              <td className="px-3 py-2 text-[var(--mute)]">{asText(element?.description, "—")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
                <div>
                  <h5 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">Behavior</h5>
                  <ul className="list-disc space-y-1 pl-5 font-mono text-xs leading-5 text-[var(--text)]">
                    {asList(item?.behavior).length === 0 && <li className="list-none text-[var(--mute)]">No behavior recorded.</li>}
                    {asList(item?.behavior).map((line, lineIndex) => (
                      <li key={lineIndex}>{asText(line)}</li>
                    ))}
                  </ul>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h5 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">Constraints</h5>
                    <ul className="list-disc space-y-1 pl-5 font-mono text-xs text-[var(--text)]">
                      {asList(item?.constraints).length === 0 && <li className="list-none text-[var(--mute)]">None recorded.</li>}
                      {asList(item?.constraints).map((line, lineIndex) => (
                        <li key={lineIndex}>{asText(line)}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h5 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--mute)]">Spec references</h5>
                    <ul className="list-disc space-y-1 pl-5 font-mono text-xs text-[var(--text)]">
                      {asList(item?.spec_references).length === 0 && <li className="list-none text-[var(--mute)]">None recorded.</li>}
                      {asList(item?.spec_references).map((line, lineIndex) => (
                        <li key={lineIndex}>{asText(line)}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
