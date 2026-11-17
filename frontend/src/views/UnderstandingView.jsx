import { asList, asText } from "../lib/format";

function Block({ title, children }) {
  return (
    <section className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4">
      <h4 className="mb-3 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">{title}</h4>
      {children}
    </section>
  );
}

function Items({ values, ordered = false, empty = "None recorded." }) {
  const items = asList(values);
  if (!items.length) return <p className="font-mono text-xs text-[var(--mute)]">{empty}</p>;
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag className={`space-y-1.5 font-mono text-xs leading-6 text-[var(--text)] ${ordered ? "list-decimal pl-5" : "list-disc pl-5"}`}>
      {items.map((item, index) => (
        <li key={`${index}-${String(item).slice(0, 24)}`}>{asText(item)}</li>
      ))}
    </Tag>
  );
}

export default function UnderstandingView({ data }) {
  const record = data && typeof data === "object" && !Array.isArray(data) ? data : {};
  return (
    <div className="grid gap-4">
      <Block title="System overview">
        <p className="font-mono text-xs leading-6 text-[var(--text)]">{asText(record.system_purpose)}</p>
      </Block>
      <Block title="Major components">
        {asList(record.major_components).length === 0 ? (
          <p className="font-mono text-xs text-[var(--mute)]">No components recorded.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {asList(record.major_components).map((item, index) => (
              <div key={`${index}-${item}`} className="rounded-lg border border-[var(--line)] bg-[rgba(125,211,252,0.05)] px-3 py-2 font-mono text-xs font-medium text-[var(--acc)]">
                {asText(item)}
              </div>
            ))}
          </div>
        )}
      </Block>
      <div className="grid gap-4 lg:grid-cols-2">
        <Block title="Inputs">
          <Items values={record.inputs} />
        </Block>
        <Block title="Outputs">
          <Items values={record.outputs} />
        </Block>
      </div>
      <Block title="Functional requirements">
        <Items values={record.functional_requirements} ordered />
      </Block>
      <Block title="Constraints">
        <Items values={record.constraints} />
      </Block>
      <Block title="Ambiguities">
        {asList(record.ambiguities).length === 0 ? (
          <p className="font-mono text-xs text-[var(--mute)]">No ambiguities recorded.</p>
        ) : (
          <div className="space-y-2">
            {asList(record.ambiguities).map((item, index) => (
              <div
                key={`${index}-${String(item).slice(0, 20)}`}
                className="rounded-lg border border-[rgba(251,191,36,0.3)] bg-[rgba(251,191,36,0.07)] px-3 py-2 font-mono text-xs leading-6 text-[var(--warn)]"
              >
                {asText(item)}
              </div>
            ))}
          </div>
        )}
      </Block>
    </div>
  );
}
