import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import AgentBoard from "../components/AgentBoard";
import RtlChip from "../components/RtlChip";
import RunSummary from "../components/RunSummary";
import UploadPanel from "../components/UploadPanel";
import { useRuns } from "../context/RunContext";

/** Metric chip: icon + value + label */
function MetricChip({ icon, value, label, color }) {
  const colorMap = {
    purple: { val: "text-[#35145D]" },
    blue:   { val: "text-[#1E3A8A]" },
    green:  { val: "text-[#065F46]" },
    amber:  { val: "text-[#92400E]" },
  };
  const c = colorMap[color] || colorMap.purple;
  return (
    <div className="glass flex items-center gap-3 px-4 py-3">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#EFE5FC] text-[#7540C5] text-base">
        {icon}
      </span>
      <div>
        <div className={`text-lg font-bold leading-none ${c.val}`}>{value}</div>
        <div className="mt-0.5 text-xs font-medium text-muted">{label}</div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { active, runs } = useRuns();

  // Compute metric values
  const totalRuns = runs.length;
  const verifiedCount = runs.filter(
    (r) => r.summary?.rtl_verification_valid === true
  ).length;

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
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#A879E5]">SPEC2RTL</p>
        <h1 className="mt-1 flex items-center gap-2.5 text-3xl font-bold tracking-tight text-indigo">
          <span>Welcome back</span>
          <Sparkles size={24} className="text-[#7540C5]" aria-hidden="true" />
        </h1>
        <p className="mt-1.5 text-sm leading-6 text-muted">
          Run the multi-agent specification-to-RTL pipeline
        </p>
      </div>

      {/* ── Metric chips row ──────────────────────────────── */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricChip icon="⚡" value="7" label="Agents" color="purple" />
        <MetricChip icon="▶" value={totalRuns} label="Runs" color="blue" />
        <MetricChip icon="✓" value={verifiedCount} label="Verified" color="green" />
        <MetricChip icon="⏱" value={avgTime} label="Avg. Time" color="amber" />
      </div>

      {/* ── Hero glass card: upload + 3D chip ────────────── */}
      <div
        className="glass mb-6 overflow-hidden"
        style={{
          background:
            "linear-gradient(135deg, rgba(255,255,255,0.80) 0%, rgba(233,221,251,0.65) 55%, rgba(224,242,254,0.60) 100%)",
        }}
      >
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
        <div className="glass mb-6 px-5 py-4 text-sm text-muted">
          Pipeline progress will appear here after a specification is submitted.
        </div>
      )}

      {/* ── Agent pipeline header ─────────────────────────── */}
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-indigo">Pipeline Agents</h2>
        {active && (
          <Link to="/results" className="text-sm font-semibold text-[#7540C5] hover:text-[#35145D]">
            Open full results →
          </Link>
        )}
      </div>

      {/* ── AgentBoard ───────────────────────────────────── */}
      <AgentBoard run={active} />
    </div>
  );
}
