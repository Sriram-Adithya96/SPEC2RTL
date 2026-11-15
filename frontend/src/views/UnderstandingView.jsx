import { asList, asText } from "../lib/format";

function Block({ title, children }) {
  return (
    <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
      <h4 className="mb-3 text-sm font-bold text-indigo">{title}</h4>
      {children}
    </section>
  );
}

function Items({ values, ordered = false, empty = "None recorded." }) {
  const items = asList(values);
  if (!items.length) return <p className="text-sm text-muted">{empty}</p>;
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag className={`space-y-2 text-sm leading-6 text-[#4A3566] ${ordered ? "list-decimal pl-5" : "list-disc pl-5"}`}>
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
        <p className="text-sm leading-6 text-[#4A3566]">{asText(record.system_purpose)}</p>
      </Block>
      <Block title="Major components">
        {asList(record.major_components).length === 0 ? (
          <p className="text-sm text-muted">No components recorded.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {asList(record.major_components).map((item, index) => (
              <div key={`${index}-${item}`} className="rounded-xl bg-[#F8F5FF] px-3 py-2 text-sm font-medium text-indigo">
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
          <p className="text-sm text-muted">No ambiguities recorded.</p>
        ) : (
          <div className="space-y-2">
            {asList(record.ambiguities).map((item, index) => (
              <div key={`${index}-${String(item).slice(0, 20)}`} className="rounded-xl border border-[#E7D7A1] bg-[#FFF8EA] px-3 py-2 text-sm leading-6 text-[#7A5B12]">
                {asText(item)}
              </div>
            ))}
          </div>
        )}
      </Block>
    </div>
  );
}
