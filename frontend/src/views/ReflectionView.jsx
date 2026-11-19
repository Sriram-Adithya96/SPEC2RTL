import { useEffect, useState } from "react";

function Block({ title, children }) {
  return (
    <section className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4">
      <h4 className="mb-3 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">{title}</h4>
      {children}
    </section>
  );
}

function VerificationAttemptCard({ data, label }) {
  const result = data && typeof data === "object" && !Array.isArray(data) ? data : {};
  const valid = result.valid;
  const issues = Array.isArray(result.issues) ? result.issues : [];
  const tone =
    valid === true
      ? "border-[rgba(74,222,128,0.3)] bg-[rgba(74,222,128,0.07)]"
      : valid === false
        ? "border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.07)]"
        : "border-[var(--line)] bg-[rgba(16,22,32,0.4)]";
  const pill =
    valid === true
      ? "bg-[rgba(74,222,128,0.15)] text-[var(--ok)]"
      : valid === false
        ? "bg-[rgba(248,113,113,0.15)] text-[var(--bad)]"
        : "bg-[rgba(125,138,163,0.1)] text-[var(--mute)]";
  const statusText = valid === true ? "Passed" : valid === false ? "Failed" : "Unknown";
  return (
    <div className={`rounded-xl border p-3 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-xs font-semibold text-[var(--text)]">{label}</span>
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 font-mono text-[11px] font-bold ${pill}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {statusText}
        </span>
      </div>
      {issues.length > 0 && (
        <ul className="mt-2 list-disc pl-5 font-mono text-xs text-[var(--bad)]">
          {issues.slice(0, 4).map((issue, i) => (
            <li key={i}>{String(issue)}</li>
          ))}
          {issues.length > 4 && (
            <li className="text-[var(--mute)]">and {issues.length - 4} more issue(s)</li>
          )}
        </ul>
      )}
      {issues.length === 0 && valid !== undefined && (
        <p className="mt-1 font-mono text-xs text-[var(--mute)]">
          {valid ? "No issues found." : "No issue details recorded."}
        </p>
      )}
    </div>
  );
}

function ReflectionAttemptCard({ data, label }) {
  const result = data && typeof data === "object" && !Array.isArray(data) ? data : {};
  const needsRevision = result.needs_revision;
  const feedback = typeof result.feedback === "string" ? result.feedback : "";
  const componentFeedback =
    result.component_feedback &&
    typeof result.component_feedback === "object" &&
    !Array.isArray(result.component_feedback)
      ? result.component_feedback
      : {};
  const componentEntries = Object.entries(componentFeedback);
  const tone =
    needsRevision === true
      ? "border-[rgba(251,191,36,0.3)] bg-[rgba(251,191,36,0.07)]"
      : needsRevision === false
        ? "border-[rgba(74,222,128,0.3)] bg-[rgba(74,222,128,0.07)]"
        : "border-[var(--line)] bg-[rgba(16,22,32,0.4)]";
  return (
    <div className={`rounded-xl border p-3 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-xs font-semibold text-[var(--text)]">{label}</span>
        <span
          className={`rounded-full px-2.5 py-1 font-mono text-[11px] font-bold ${
            needsRevision === true
              ? "bg-[rgba(251,191,36,0.15)] text-[var(--warn)]"
              : needsRevision === false
                ? "bg-[rgba(74,222,128,0.15)] text-[var(--ok)]"
                : "bg-[rgba(125,138,163,0.1)] text-[var(--mute)]"
          }`}
        >
          {needsRevision === true ? "Revision Required" : needsRevision === false ? "No Revision Needed" : "Unknown"}
        </span>
      </div>
      {feedback && (
        <p className="mt-2 font-mono text-xs leading-5 text-[var(--mute)]">
          {feedback.length > 300 ? feedback.slice(0, 300) + "…" : feedback}
        </p>
      )}
      {componentEntries.length > 0 && (
        <div className="mt-2 grid gap-1">
          {componentEntries.map(([comp, fb]) => (
            <div key={comp} className="rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.5)] px-2 py-1.5">
              <span className="font-mono text-xs font-bold text-[var(--acc2)]">{comp}: </span>
              <span className="font-mono text-xs text-[var(--mute)]">{String(fb)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ReflectionView({ data, runId }) {
  const result = data && typeof data === "object" && !Array.isArray(data) ? data : {};
  const needsRevision = result.needs_revision;
  const feedback = typeof result.feedback === "string" ? result.feedback : "";
  const componentFeedback =
    result.component_feedback &&
    typeof result.component_feedback === "object" &&
    !Array.isArray(result.component_feedback)
      ? result.component_feedback
      : {};
  const reasoning = typeof result.reasoning === "string" ? result.reasoning : "";
  const componentEntries = Object.entries(componentFeedback);

  const [attemptHistory, setAttemptHistory] = useState([]);
  const [loadingAttempts, setLoadingAttempts] = useState(false);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function loadAttempts() {
      setLoadingAttempts(true);
      const loaded = [];
      const indexResponse = await fetch(`/api/runs/${runId}/outputs`);
      if (!indexResponse.ok) throw new Error("Could not list run outputs.");
      const index = await indexResponse.json();
      const available = new Set(index.files || []);
      for (let n = 1; n <= 3; n++) {
        const reflectionFile = `reflection_attempt_${n}.json`;
        const verificationFile = `rtl_verification_attempt_${n}.json`;
        const hasReflection = available.has(reflectionFile);
        const hasVerification = available.has(verificationFile);
        if (!hasReflection && !hasVerification) break;
        const [refResp, verResp] = await Promise.all([
          hasReflection
            ? fetch(`/api/runs/${runId}/download/${reflectionFile}`)
            : Promise.resolve(null),
          hasVerification
            ? fetch(`/api/runs/${runId}/download/${verificationFile}`)
            : Promise.resolve(null),
        ]);
        const refData = refResp?.ok ? await refResp.json().catch(() => null) : null;
        const verData = verResp?.ok ? await verResp.json().catch(() => null) : null;
        if (refData || verData) loaded.push({ n, reflection: refData, verification: verData });
      }
      if (!cancelled) {
        setAttemptHistory(loaded);
        setLoadingAttempts(false);
      }
    }
    loadAttempts().catch(() => setLoadingAttempts(false));
    return () => { cancelled = true; };
  }, [runId]);

  const headerBorder =
    needsRevision === true
      ? "border-[rgba(251,191,36,0.35)]"
      : needsRevision === false
        ? "border-[rgba(74,222,128,0.35)]"
        : "border-[var(--line)]";

  const statusPill =
    needsRevision === true
      ? "bg-[rgba(251,191,36,0.15)] text-[var(--warn)] border border-[rgba(251,191,36,0.4)]"
      : needsRevision === false
        ? "bg-[rgba(74,222,128,0.15)] text-[var(--ok)] border border-[rgba(74,222,128,0.4)]"
        : "bg-[rgba(125,138,163,0.1)] text-[var(--mute)] border border-[var(--line)]";

  const hasData = feedback || componentEntries.length > 0 || reasoning;

  return (
    <div className="grid gap-4">
      <section className={`rounded-xl border ${headerBorder} bg-[rgba(16,22,32,0.6)] p-5`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">Reflection Analysis</h4>
            <p className="mt-1 max-w-xl font-mono text-xs leading-5 text-[var(--mute)]">
              Analyses RTL verification failures and generates targeted correction feedback for the RTL Generation Agent.
            </p>
          </div>
          <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-mono text-xs font-bold ${statusPill}`}>
            <span className="h-2 w-2 rounded-full bg-current" />
            {needsRevision === true ? "Revision Required" : needsRevision === false ? "No Revision Needed" : "Pending"}
          </span>
        </div>
      </section>

      {!hasData && (
        <Block title="No reflection data">
          <p className="font-mono text-xs text-[var(--mute)]">
            Reflection output is not available for this run. This agent is skipped when RTL verification passes without requiring corrections.
          </p>
        </Block>
      )}

      {feedback && (
        <Block title="Reflection Feedback">
          <p className="whitespace-pre-wrap font-mono text-xs leading-5 text-[var(--text)]">{feedback}</p>
        </Block>
      )}

      {componentEntries.length > 0 && (
        <Block title="Component-Specific Feedback">
          <div className="grid gap-3">
            {componentEntries.map(([component, fb]) => (
              <div key={component} className="rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-4 py-3">
                <div className="mb-1 font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--acc2)]">
                  {component}
                </div>
                <p className="font-mono text-xs leading-5 text-[var(--text)]">{String(fb)}</p>
              </div>
            ))}
          </div>
        </Block>
      )}

      {reasoning && (
        <Block title="Reflection Reasoning">
          <p className="whitespace-pre-wrap font-mono text-xs leading-5 text-[var(--text)]">{reasoning}</p>
        </Block>
      )}

      {(attemptHistory.length > 0 || loadingAttempts) && (
        <section className="rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.6)] p-4">
          <h4 className="mb-3 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">Retry Attempt History</h4>
          {loadingAttempts && (
            <p className="font-mono text-xs text-[var(--mute)]">Loading attempt history…</p>
          )}
          {attemptHistory.length > 0 && (
            <div className="grid gap-4">
              {attemptHistory.map((item) => (
                <div key={item.n} className="grid gap-2">
                  <div className="font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--acc2)]">
                    Attempt {item.n}
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {item.verification && (
                      <VerificationAttemptCard data={item.verification} label={`Re-verification ${item.n}`} />
                    )}
                    {item.reflection && (
                      <ReflectionAttemptCard data={item.reflection} label={`Reflection ${item.n}`} />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
