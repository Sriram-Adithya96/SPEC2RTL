import { Square } from "lucide-react";
import { useRuns } from "../context/RunContext";
import { formatTime, formatTokensCompact, stageProgress } from "../lib/format";
import ErrorBanner from "./ErrorBanner";
import StatusBadge from "./StatusBadge";

export default function RunSummary({ run }) {
  const { cancelRun } = useRuns();
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
          <div className="font-mono text-xs font-semibold uppercase tracking-wider text-[var(--mute)]">Current run</div>
          <h2 className="mt-1 font-mono text-lg font-bold text-[var(--text)]">{run.filename || "Specification"}</h2>
          <p className="mt-1 font-mono text-xs text-[var(--mute)]">
            Started {formatTime(run.started_at)}
            {run.finished_at ? ` · Finished ${formatTime(run.finished_at)}` : ""}
            {run.source === "cli" ? " · Command-line run" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          {run.status === "running" && (
            <button
              type="button"
              onClick={() => cancelRun(run.run_id)}
              className="inline-flex items-center gap-1.5 rounded-full border border-[rgba(248,113,113,0.4)] bg-[rgba(248,113,113,0.15)] px-3 py-1 font-mono text-[11px] font-bold text-[var(--bad)] hover:bg-[rgba(248,113,113,0.25)] hover:border-[var(--bad)] transition shadow-sm"
              title="Stop this active pipeline run"
            >
              <Square size={10} className="fill-[var(--bad)]" />
              Stop Pipeline
            </button>
          )}
          <StatusBadge status={run.status || "pending"} />
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-4">
        <div className="mb-1.5 flex justify-between font-mono text-xs font-semibold text-[var(--mute)]">
          <span>{run.ingestion === "running" ? "Reading specification" : "Pipeline progress"}</span>
          <span className="text-[var(--acc)]">{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[#1b2535] border border-[var(--line)]/50">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${progress}%`,
              background: "linear-gradient(90deg, var(--acc2, #a78bfa), var(--acc, #7dd3fc))",
              boxShadow: "0 0 12px rgba(125, 211, 252, 0.4)",
            }}
          />
        </div>
      </div>

      {/* Stat chips */}
      <div className={`mt-4 grid grid-cols-1 gap-3 ${run.token_usage?.total_tokens > 0 ? "sm:grid-cols-2 lg:grid-cols-4" : "sm:grid-cols-3"}`}>
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
        {run.token_usage?.total_tokens > 0 && (
          <StatChip
            label="Total Tokens"
            value={formatTokensCompact(run.token_usage.total_tokens)}
            subtext={`${formatTokensCompact(run.token_usage.prompt_tokens)} in · ${formatTokensCompact(run.token_usage.completion_tokens)} out`}
            color="cyan"
          />
        )}
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

function StatChip({ label, value, subtext, color }) {
  const colorMap = {
    purple: "bg-[rgba(167,139,250,0.08)] border border-[rgba(167,139,250,0.25)] text-[var(--acc2)]",
    cyan:   "bg-[rgba(125,211,252,0.08)] border border-[rgba(125,211,252,0.25)] text-[var(--acc)]",
    green:  "bg-[rgba(74,222,128,0.08)] border border-[rgba(74,222,128,0.25)] text-[var(--ok)]",
    red:    "bg-[rgba(248,113,113,0.08)] border border-[rgba(248,113,113,0.25)] text-[var(--bad)]",
    amber:  "bg-[rgba(251,191,36,0.08)] border border-[rgba(251,191,36,0.25)] text-[var(--warn)]",
    muted:  "bg-[rgba(125,138,163,0.06)] border border-[var(--line)] text-[var(--mute)]",
  };
  const cls = colorMap[color] || colorMap.muted;
  return (
    <div className={`rounded-xl px-4 py-3 ${cls}`}>
      <div className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--mute)]">{label}</div>
      <div className="mt-1 font-mono text-xl font-bold">{value ?? "—"}</div>
      {subtext && <div className="mt-0.5 font-mono text-[10px] opacity-75">{subtext}</div>}
    </div>
  );
}
