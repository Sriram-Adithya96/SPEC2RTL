function Block({ title, children }) {
  return (
    <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
      <h4 className="mb-3 text-sm font-bold text-indigo">{title}</h4>
      {children}
    </section>
  );
}

function StatTile({ label, value }) {
  return (
    <div className="rounded-xl bg-white/70 px-3 py-2 text-center">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 text-xl font-bold text-indigo">{value ?? "—"}</div>
    </div>
  );
}

export default function RTLVerificationView({ data }) {
  const result =
    data && typeof data === "object" && !Array.isArray(data) ? data : {};
  const valid = result.valid;
  const issues = Array.isArray(result.issues) ? result.issues : [];
  const suggestions = Array.isArray(result.suggestions) ? result.suggestions : [];
  const reasoning = typeof result.reasoning === "string" ? result.reasoning : "";

  const statusText =
    valid === true ? "Passed" : valid === false ? "Failed" : "Pending";

  const headerTone =
    valid === true
      ? "border-[#b8e86a]/60 bg-[#f5fde8]"
      : valid === false
        ? "border-[#F3C0C0] bg-[#FFF6F6]"
        : "border-[#E9DDFB] bg-white";

  const statusPill =
    valid === true
      ? "bg-[#C8F52F] text-[#35145D]"
      : valid === false
        ? "bg-[#FDECEC] text-[#B42318]"
        : "bg-[#E9DDFB] text-[#4A3566]";

  return (
    <div className="grid gap-4">
      <section className={`rounded-2xl border p-5 ${headerTone}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="text-sm font-bold text-indigo">RTL Verification Result</h4>
            <p className="mt-1 max-w-xl text-sm leading-6 text-muted">
              Checks the generated Verilog RTL against the original hardware
              specification for correctness and completeness.
            </p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-bold ${statusPill}`}
          >
            <span className="h-2 w-2 rounded-full bg-current" />
            {statusText}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-3">
          <StatTile label="Issues" value={issues.length} />
          <StatTile label="Suggestions" value={suggestions.length} />
          <StatTile label="Result" value={statusText} />
        </div>
      </section>

      <section
        className={`rounded-2xl border p-4 ${
          issues.length > 0
            ? "border-[#F3C0C0] bg-[#FFF6F6]"
            : "border-[#E9DDFB] bg-white"
        }`}
      >
        <h4
          className={`mb-2 text-sm font-bold ${
            issues.length > 0 ? "text-[#B42318]" : "text-indigo"
          }`}
        >
          Verification Issues
          {issues.length > 0 && (
            <span className="ml-2 rounded-full bg-[#FDECEC] px-2 py-0.5 text-xs font-bold text-[#B42318]">
              {issues.length}
            </span>
          )}
        </h4>
        {issues.length === 0 ? (
          <p className="text-sm text-muted">
            {valid === true
              ? "No issues — the RTL matches the specification."
              : "No issues were recorded."}
          </p>
        ) : (
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-[#8F1D1D]">
            {issues.map((issue, i) => (
              <li key={i}>
                {typeof issue === "string" ? issue : JSON.stringify(issue)}
              </li>
            ))}
          </ul>
        )}
      </section>

      {suggestions.length > 0 && (
        <section className="rounded-2xl border border-[#E7D7A1] bg-[#FFF8EA] p-4">
          <h4 className="mb-2 text-sm font-bold text-[#7A5B12]">
            Suggestions for Correction
            <span className="ml-2 rounded-full bg-[#F5E6B2] px-2 py-0.5 text-xs font-bold text-[#7A5B12]">
              {suggestions.length}
            </span>
          </h4>
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-[#7A5B12]">
            {suggestions.map((s, i) => (
              <li key={i}>{typeof s === "string" ? s : JSON.stringify(s)}</li>
            ))}
          </ul>
        </section>
      )}

      {reasoning && (
        <Block title="Verification Reasoning">
          <p className="text-sm leading-6 text-[#4A3566]">{reasoning}</p>
        </Block>
      )}

      {!reasoning && issues.length === 0 && suggestions.length === 0 && valid === undefined && (
        <Block title="No data">
          <p className="text-sm text-muted">
            RTL verification output is not available for this run.
          </p>
        </Block>
      )}
    </div>
  );
}

