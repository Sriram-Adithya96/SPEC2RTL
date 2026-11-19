import { formatTime, stageProgress } from "../lib/format";
import ErrorBanner from "./ErrorBanner";
import StatusBadge from "./StatusBadge";

export default function RunSummary({ run }) {
  if (!run) return null;
  const progress = stageProgress(run);
  const summary = run.summary;

  const rtlVerifValid = summary?.rtl_verification_valid;
  const rtlVerifStatus = run.agents?.rtl_verification?.status;
  let rtlVerifLabel = "—";
  if (rtlVerifValid === true) rtlVerifLabel = "Passed ✓";
  else if (rtlVerifValid === false) rtlVerifLabel = "Failed ✗";
  else if (rtlVerifStatus === "running") rtlVerifLabel = "Running";
  else if (rtlVerifStatus === "pending") rtlVerifLabel = "Pending";

  const reflectionStatus = run.agents?.reflection?.status;
  let reflectionLabel = "—";
  if (reflectionStatus === "skipped") reflectionLabel = "Skipped";
  else if (reflectionStatus === "completed") reflectionLabel = "Used";
  else if (reflectionStatus === "failed") reflectionLabel = "Failed";
  else if (reflectionStatus === "running") reflectionLabel = "Running";
  else if (reflectionStatus === "pending") reflectionLabel = "Pending";

  return (
    <section className="glass mb-6 p-5">
      {/* Run header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-muted">Current run</div>
          <h2 className="mt-1 text-lg font-bold text-indigo">{run.filename || "Specification"}</h2>
          <p className="mt-1 text-xs text-muted">
            Started {formatTime(run.started_at)}
            {run.finished_at ? ` · Finished ${formatTime(run.finished_at)}` : ""}
            {run.source === "cli" ? " · Command-line run" : ""}
          </p>
        </div>
        <StatusBadge status={run.status || "pending"} />
      </div>

      {/* Progress bar */}
      <div className="mt-4">
        <div className="mb-1.5 flex justify-between text-xs font-semibold text-muted">
          <span>{run.ingestion === "running" ? "Reading specification" : "Pipeline progress"}</span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[#E9DDFB]">
          <div
            className="h-full rounded-full bg-[#7540C5] shadow-glow transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Stat chips */}
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatChip
          label="Components described"
          value={summary?.components_described}
          color="purple"
        />
        <StatChip
          label="RTL verification"
          value={rtlVerifLabel}
          color={rtlVerifValid === true ? "green" : rtlVerifValid === false ? "red" : "muted"}
        />
        <StatChip
          label="Reflection"
          value={reflectionLabel}
          color={
            reflectionStatus === "completed"
              ? "amber"
              : reflectionStatus === "skipped" || !reflectionStatus
              ? "muted"
              : "purple"
          }
        />
      </div>

      {/* Error */}
      {run.error && (
        <div className="mt-4">
          <ErrorBanner
            title={`Pipeline failed${run.failed_stage ? ` during ${run.failed_stage}` : ""}`}
            error={run.error}
          />
        </div>
      )}
    </section>
  );
}

function StatChip({ label, value, color }) {
  const colorMap = {
    purple: "bg-[#EDE8FA] text-[#35145D]",
    green:  "bg-[#D1FAE5] text-[#065F46]",
    red:    "bg-[#FEE2E2] text-[#991B1B]",
    amber:  "bg-[#FEF3C7] text-[#92400E]",
    muted:  "bg-[#F8F5FF] text-muted",
  };
  const cls = colorMap[color] || colorMap.muted;
  return (
    <div className={`rounded-2xl px-4 py-3 ${cls}`}>
      <div className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</div>
      <div className="mt-1 text-xl font-bold">{value ?? "—"}</div>
    </div>
  );
}
