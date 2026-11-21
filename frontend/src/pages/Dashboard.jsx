import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import AgentBoard from "../components/AgentBoard";
import RtlChip from "../components/RtlChip";
import RunSummary from "../components/RunSummary";
import UploadPanel from "../components/UploadPanel";
import { useRuns } from "../context/RunContext";
import { formatTokensCompact } from "../lib/format";

/** Metric chip: icon + value + label */
function MetricChip({ icon, value, label, color }) {
  const colorMap = {
    purple: { val: "text-[var(--acc2)]" },
    blue:   { val: "text-[var(--acc)]" },
    green:  { val: "text-[var(--ok)]" },
    amber:  { val: "text-[var(--warn)]" },
  };
  const c = colorMap[color] || colorMap.purple;
  return (
    <div className="glass flex items-center gap-3 px-4 py-3">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[rgba(125,211,252,0.1)] text-[var(--acc)] text-sm">
        {icon}
      </span>
      <div>
        <div className={`font-mono text-xl font-bold leading-none ${c.val}`}>{value}</div>
        <div className="mt-1 font-mono text-xs text-[var(--mute)]">{label}</div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { active, runs } = useRuns();

  // Compute metric values
  const totalRuns = runs.length;
  const verifiedCount = runs.filter(
    (r) =>
      r.summary?.rtl_verification === "passed" ||
      r.summary?.rtl_verification_valid === true ||
      r.agents?.rtl_verification?.status === "passed" ||
      r.agents?.rtl_verification?.status === "completed",
  ).length;
  const totalTokens = runs.reduce(
    (acc, r) => acc + (r.token_usage?.total_tokens || 0),
    0
  );

  // Average pipeline time (minutes)
  const completedWithTime = runs.filter(
    (r) => r.started_at && r.finished_at && r.status === "completed"
  );
  let avgTime = "—";
  if (completedWithTime.length > 0) {
    const totalMs = completedWithTime.reduce((acc, r) => {
      return acc + (new Date(r.finished_at) - new Date(r.started_at));
    }, 0);
    const avgMin = (totalMs / completedWithTime.length / 60000).toFixed(1);
    avgTime = `${avgMin} min`;
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 md:px-8 md:py-8">

      {/* ── Hero section ─────────────────────────────────── */}
      <div className="mb-6">
        <p className="font-mono text-xs font-bold uppercase tracking-[0.16em] text-[var(--acc2)]">SPEC2RTL</p>
        <h1 className="mt-1 flex items-center gap-2.5 font-mono text-2xl md:text-3xl font-extrabold tracking-tight text-[var(--text)]">
          <span>SPECIFICATION &rarr; VERILOG PIPELINE</span>
          <Sparkles size={22} className="text-[var(--acc)]" aria-hidden="true" />
        </h1>
        <p className="mt-1.5 text-xs text-[var(--mute)]">
          Autonomous multi-agent synthesis from specification to verified SystemVerilog RTL
        </p>
      </div>

      {/* ── Metric chips row ──────────────────────────────── */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricChip icon="⚡" value="7" label="Pipeline Stages" color="purple" />
        <MetricChip icon="▶" value={totalRuns} label="Total Runs" color="blue" />
        <MetricChip icon="✓" value={verifiedCount} label="Verified RTL" color="green" />
        {totalTokens > 0 ? (
          <MetricChip icon="🪙" value={formatTokensCompact(totalTokens)} label="Total Tokens" color="amber" />
        ) : (
          <MetricChip icon="⏱" value={avgTime} label="Avg. Runtime" color="amber" />
        )}
      </div>

      {/* ── Hero glass card: upload + 3D chip ────────────── */}
      <div className="glass mb-6 overflow-hidden">
        <div className="flex flex-col gap-6 p-6 md:flex-row md:items-center md:p-8">
          {/* Upload section */}
          <div className="flex-1 min-w-0">
            <UploadPanel />
          </div>
          {/* 3D chip — hidden on small screens */}
          <div className="hidden shrink-0 md:flex md:items-center md:justify-center md:w-52">
            <div className="chip-float flex items-center justify-center select-none" aria-hidden="true">
              <RtlChip />
            </div>
          </div>
        </div>
      </div>

      {/* ── Current run summary ───────────────────────────── */}
      {active ? (
        <RunSummary run={active} />
      ) : (
        <div className="glass mb-6 px-5 py-4 font-mono text-xs text-[var(--mute)]">
          Pipeline progress will appear here after a specification is submitted.
        </div>
      )}

      {/* ── Agent pipeline header ─────────────────────────── */}
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-mono text-base font-bold text-[var(--text)]">Pipeline Agents</h2>
        {active && (
          <Link to="/results" className="font-mono text-xs font-semibold text-[var(--acc)] hover:underline">
            Open full results →
          </Link>
        )}
      </div>

      {/* ── AgentBoard ───────────────────────────────────── */}
      <AgentBoard run={active} />
    </div>
  );
}
