import { useEffect, useState } from "react";

function Block({ title, children }) {
  return (
    <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
      <h4 className="mb-3 text-sm font-bold text-indigo">{title}</h4>
      {children}
    </section>
  );
}

function VerificationAttemptCard({ data, label }) {
  const result =
    data && typeof data === "object" && !Array.isArray(data) ? data : {};
  const valid = result.valid;
  const issues = Array.isArray(result.issues) ? result.issues : [];
  const tone =
    valid === true
      ? "border-[#b8e86a]/60 bg-[#f5fde8]"
      : valid === false
        ? "border-[#F3C0C0] bg-[#FFF6F6]"
        : "border-[#E9DDFB] bg-white";
  const pill =
    valid === true
      ? "bg-[#C8F52F] text-[#35145D]"
      : valid === false
        ? "bg-[#FDECEC] text-[#B42318]"
        : "bg-[#E9DDFB] text-[#4A3566]";
  const statusText = valid === true ? "Passed" : valid === false ? "Failed" : "Unknown";
  return (
    <div className={`rounded-xl border p-3 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-indigo">{label}</span>
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${pill}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {statusText}
        </span>
      </div>
      {issues.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-[#8F1D1D]">
          {issues.slice(0, 4).map((issue, i) => (
            <li key={i}>{String(issue)}</li>
          ))}
          {issues.length > 4 && (
            <li className="text-muted">and {issues.length - 4} more issue(s)</li>
          )}
        </ul>
      )}
      {issues.length === 0 && valid !== undefined && (
        <p className="mt-1 text-xs text-muted">
          {valid ? "No issues found." : "No issue details recorded."}
        </p>
      )}
    </div>
  );
}

function ReflectionAttemptCard({ data, label }) {
  const result =
    data && typeof data === "object" && !Array.isArray(data) ? data : {};
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
      ? "border-[#E7D7A1] bg-[#FFF8EA]"
      : needsRevision === false
        ? "border-[#b8e86a]/60 bg-[#f5fde8]"
        : "border-[#E9DDFB] bg-white";
  return (
    <div className={`rounded-xl border p-3 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-indigo">{label}</span>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-bold ${
            needsRevision === true
              ? "bg-[#FFF3CD] text-[#9A6700]"
              : needsRevision === false
                ? "bg-[#C8F52F] text-[#35145D]"
                : "bg-[#E9DDFB] text-[#4A3566]"
          }`}
        >
          {needsRevision === true
            ? "Revision Required"
            : needsRevision === false
              ? "No Revision Needed"
              : "Unknown"}
        </span>
      </div>
      {feedback && (
        <p className="mt-2 text-xs leading-5 text-[#4A3566]">
          {feedback.length > 300 ? feedback.slice(0, 300) + "…" : feedback}
        </p>
      )}
      {componentEntries.length > 0 && (
        <div className="mt-2 grid gap-1">
          {componentEntries.map(([comp, fb]) => (
            <div key={comp} className="rounded-lg bg-white/60 px-2 py-1.5">
              <span className="text-xs font-bold text-[#7540C5]">{comp}: </span>
              <span className="text-xs text-[#4A3566]">{String(fb)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ReflectionView({ data, runId }) {
  const result =
    data && typeof data === "object" && !Array.isArray(data) ? data : {};
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
      for (let n = 1; n <= 2; n++) {
        try {
          const [refResp, verResp] = await Promise.all([
            fetch("/api/runs/" + runId + "/download/reflection_attempt_" + n + ".json"),
            fetch("/api/runs/" + runId + "/download/rtl_verification_attempt_" + n + ".json"),
          ]);
          const refOk = refResp.ok;
          const verOk = verResp.ok;
          if (!refOk && !verOk) break;
          const refData = refOk ? await refResp.json().catch(function() { return null; }) : null;
          const verData = verOk ? await verResp.json().catch(function() { return null; }) : null;
          if (refData || verData) {
            loaded.push({ n: n, reflection: refData, verification: verData });
          }
        } catch (_e) {
          break;
        }
      }
      if (!cancelled) {
        setAttemptHistory(loaded);
        setLoadingAttempts(false);
      }
    }

    loadAttempts().catch(function() { setLoadingAttempts(false); });
    return function() { cancelled = true; };
  }, [runId]);

  const headerTone =
    needsRevision === true
      ? "border-[#E7D7A1] bg-[#FFF8EA]"
      : needsRevision === false
        ? "border-[#b8e86a]/60 bg-[#f5fde8]"
        : "border-[#E9DDFB] bg-white";

  const hasData = feedback || componentEntries.length > 0 || reasoning;

  return (
    <div className="grid gap-4">
      <section className={`rounded-2xl border p-5 ${headerTone}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="text-sm font-bold text-indigo">Reflection Analysis</h4>
            <p className="mt-1 max-w-xl text-sm leading-6 text-muted">
              Analyses RTL verification failures and generates targeted correction
              feedback for the RTL Generation Agent.
            </p>
          </div>
          <span
            className={"inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-bold " + (
              needsRevision === true
                ? "bg-[#FFF3CD] text-[#9A6700]"
                : needsRevision === false
                  ? "bg-[#C8F52F] text-[#35145D]"
                  : "bg-[#E9DDFB] text-[#4A3566]"
            )}
          >
            <span className="h-2 w-2 rounded-full bg-current" />
            {needsRevision === true
              ? "Revision Required"
              : needsRevision === false
                ? "No Revision Needed"
                : "Pending"}
          </span>
        </div>
      </section>

      {!hasData && (
        <Block title="No reflection data">
          <p className="text-sm text-muted">
            Reflection output is not available for this run. This agent is skipped
            when RTL verification passes without requiring corrections.
          </p>
        </Block>
      )}

      {feedback && (
        <Block title="Reflection Feedback">
          <p className="whitespace-pre-wrap text-sm leading-6 text-[#4A3566]">{feedback}</p>
        </Block>
      )}

      {componentEntries.length > 0 && (
        <Block title="Component-Specific Feedback">
          <div className="grid gap-3">
            {componentEntries.map(function(entry) {
              var component = entry[0];
              var fb = entry[1];
              return (
                <div key={component} className="rounded-xl bg-[#F8F5FF] px-4 py-3">
                  <div className="mb-1 text-xs font-bold uppercase tracking-wide text-[#7540C5]">
                    {component}
                  </div>
                  <p className="text-sm leading-6 text-[#4A3566]">{String(fb)}</p>
                </div>
              );
            })}
          </div>
        </Block>
      )}

      {reasoning && (
        <Block title="Reflection Reasoning">
          <p className="whitespace-pre-wrap text-sm leading-6 text-[#4A3566]">{reasoning}</p>
        </Block>
      )}

      {(attemptHistory.length > 0 || loadingAttempts) && (
        <section className="rounded-2xl border border-[#E9DDFB] bg-white p-4">
          <h4 className="mb-3 text-sm font-bold text-indigo">Retry Attempt History</h4>
          {loadingAttempts && (
            <p className="text-sm text-muted">Loading attempt history…</p>
          )}
          {attemptHistory.length > 0 && (
            <div className="grid gap-4">
              {attemptHistory.map(function(item) {
                return (
                  <div key={item.n} className="grid gap-2">
                    <div className="text-xs font-bold uppercase tracking-wide text-[#A879E5]">
                      Attempt {item.n}
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {item.verification && (
                        <VerificationAttemptCard
                          data={item.verification}
                          label={"Re-verification " + item.n}
                        />
                      )}
                      {item.reflection && (
                        <ReflectionAttemptCard
                          data={item.reflection}
                          label={"Reflection " + item.n}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

