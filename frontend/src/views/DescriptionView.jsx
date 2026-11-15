import { useState } from "react";
import { ChevronDown } from "lucide-react";
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
        <p className="text-sm text-muted">{descriptions.length} component description(s)</p>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search components or signals"
          className="w-full rounded-xl border border-[#E9DDFB] bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#7540C5] sm:max-w-xs"
        />
      </div>
      {visible.length === 0 && <p className="text-sm text-muted">No descriptions match this search.</p>}
      {visible.map((item, index) => {
        const expanded = open === index;
        return (
          <article key={`${item?.module_name || "module"}-${index}`} className="overflow-hidden rounded-2xl border border-[#E9DDFB] bg-white">
            <button
              className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
              onClick={() => setOpen(expanded ? -1 : index)}
            >
              <span>
                <span className="block font-bold text-indigo">{asText(item?.module_name, `Component ${index + 1}`)}</span>
                <span className="block text-sm text-muted">{asText(item?.purpose, "")}</span>
              </span>
              <ChevronDown size={18} className={`shrink-0 text-[#7540C5] transition ${expanded ? "rotate-180" : ""}`} />
            </button>
            {expanded && (
              <div className="grid gap-4 border-t border-[#E9DDFB] px-4 py-4">
                <div>
                  <h5 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">Inputs</h5>
                  <SignalTable signals={item?.inputs} />
                </div>
                <div>
                  <h5 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">Outputs</h5>
                  <SignalTable signals={item?.outputs} />
                </div>
                <div>
                  <h5 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">State elements</h5>
                  {asList(item?.state_elements).length === 0 ? (
                    <p className="text-sm text-muted">No state elements recorded.</p>
                  ) : (
                    <div className="overflow-x-auto rounded-xl border border-[#E9DDFB]">
                      <table className="min-w-full text-left text-sm">
                        <thead className="bg-[#F8F5FF] text-xs uppercase tracking-wide text-muted">
                          <tr>
                            <th className="px-3 py-2">Name</th>
                            <th className="px-3 py-2">Type</th>
                            <th className="px-3 py-2">Width</th>
                            <th className="px-3 py-2">Reset</th>
                            <th className="px-3 py-2">Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {asList(item.state_elements).map((element, elementIndex) => (
                            <tr key={`${element?.name}-${elementIndex}`} className="border-t border-[#E9DDFB]">
                              <td className="px-3 py-2 font-semibold">{asText(element?.name, "—")}</td>
                              <td className="px-3 py-2">{asText(element?.type, "—")}</td>
                              <td className="px-3 py-2">{asText(element?.width, "—")}</td>
                              <td className="px-3 py-2">{asText(element?.reset_value, "—")}</td>
                              <td className="px-3 py-2">{asText(element?.description, "—")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
                <div>
                  <h5 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">Behavior</h5>
                  <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-[#4A3566]">
                    {asList(item?.behavior).length === 0 && <li className="list-none text-muted">No behavior recorded.</li>}
                    {asList(item?.behavior).map((line, lineIndex) => (
                      <li key={lineIndex}>{asText(line)}</li>
                    ))}
                  </ul>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h5 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">Constraints</h5>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-[#4A3566]">
                      {asList(item?.constraints).length === 0 && <li className="list-none text-muted">None recorded.</li>}
                      {asList(item?.constraints).map((line, lineIndex) => (
                        <li key={lineIndex}>{asText(line)}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h5 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">Specification references</h5>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-[#4A3566]">
                      {asList(item?.spec_references).length === 0 && <li className="list-none text-muted">None recorded.</li>}
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
