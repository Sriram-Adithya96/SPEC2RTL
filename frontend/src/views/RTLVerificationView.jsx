function Block({ title, children }) {
  return (
    <section className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4">
      <h4 className="mb-3 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">{title}</h4>
      {children}
    </section>
  );
}

function StatTile({ label, value }) {
  return (
    <div className="rounded-lg border border-[var(--line)] bg-[rgba(10,14,20,0.4)] px-3 py-2 text-center">
      <div className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--mute)]">{label}</div>
      <div className="mt-1 font-mono text-xl font-bold text-[var(--text)]">{value ?? "—"}</div>
    </div>
  );
}

export default function RTLVerificationView({ data }) {
  const result = data && typeof data === "object" && !Array.isArray(data) ? data : {};
  const valid = result.valid;
  const issues = Array.isArray(result.issues) ? result.issues : [];
  const suggestions = Array.isArray(result.suggestions) ? result.suggestions : [];
  const reasoning = typeof result.reasoning === "string" ? result.reasoning : "";

  const statusText = valid === true ? "Passed" : valid === false ? "Failed" : "Pending";

  const headerBorder =
    valid === true
      ? "border-[rgba(74,222,128,0.35)]"
      : valid === false
        ? "border-[rgba(248,113,113,0.35)]"
        : "border-[var(--line)]";

  const statusPill =
    valid === true
      ? "bg-[rgba(74,222,128,0.15)] text-[var(--ok)] border border-[rgba(74,222,128,0.4)]"
      : valid === false
        ? "bg-[rgba(248,113,113,0.15)] text-[var(--bad)] border border-[rgba(248,113,113,0.4)]"
        : "bg-[rgba(125,138,163,0.1)] text-[var(--mute)] border border-[var(--line)]";

  return (
    <div className="grid gap-4">
      <section className={`rounded-xl border ${headerBorder} bg-[rgba(16,22,32,0.6)] p-5`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">RTL Verification Result</h4>
            <p className="mt-1 max-w-xl font-mono text-xs leading-5 text-[var(--mute)]">
              Checks the generated Verilog RTL against the original hardware specification for correctness and completeness.
            </p>
          </div>
          <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-mono text-xs font-bold ${statusPill}`}>
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
        className={`rounded-xl border p-4 ${
          issues.length > 0
            ? "border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.07)]"
            : "border-[var(--line)] bg-[rgba(16,22,32,0.6)]"
        }`}
      >
        <h4 className={`mb-2 font-mono text-xs font-bold uppercase tracking-wider ${issues.length > 0 ? "text-[var(--bad)]" : "text-[var(--mute)]"}`}>
          Verification Issues
          {issues.length > 0 && (
            <span className="ml-2 rounded-full bg-[rgba(248,113,113,0.2)] px-2 py-0.5 font-mono text-[10px] font-bold text-[var(--bad)]">
              {issues.length}
            </span>
          )}
        </h4>
        {issues.length === 0 ? (
          <p className="font-mono text-xs text-[var(--mute)]">
            {valid === true ? "No issues — the RTL matches the specification." : "No issues were recorded."}
          </p>
        ) : (
          <ul className="list-disc space-y-1.5 pl-5 font-mono text-xs text-[var(--bad)]">
            {issues.map((issue, i) => (
              <li key={i}>{typeof issue === "string" ? issue : JSON.stringify(issue)}</li>
            ))}
          </ul>
        )}
      </section>

      {suggestions.length > 0 && (
        <section className="rounded-xl border border-[rgba(251,191,36,0.3)] bg-[rgba(251,191,36,0.07)] p-4">
          <h4 className="mb-2 font-mono text-xs font-bold uppercase tracking-wider text-[var(--warn)]">
            Suggestions for Correction
            <span className="ml-2 rounded-full bg-[rgba(251,191,36,0.2)] px-2 py-0.5 font-mono text-[10px] font-bold text-[var(--warn)]">
              {suggestions.length}
            </span>
          </h4>
          <ul className="list-disc space-y-1.5 pl-5 font-mono text-xs text-[var(--warn)]">
            {suggestions.map((s, i) => (
              <li key={i}>{typeof s === "string" ? s : JSON.stringify(s)}</li>
            ))}
          </ul>
        </section>
      )}

      {reasoning && (
        <Block title="Verification Reasoning">
          <p className="font-mono text-xs leading-5 text-[var(--text)]">{reasoning}</p>
        </Block>
      )}

      {!reasoning && issues.length === 0 && suggestions.length === 0 && valid === undefined && (
        <Block title="No data">
          <p className="font-mono text-xs text-[var(--mute)]">RTL verification output is not available for this run.</p>
        </Block>
      )}
    </div>
  );
}
