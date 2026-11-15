import { Link } from "react-router-dom";
import AgentBoard from "../components/AgentBoard";
import RunSummary from "../components/RunSummary";
import { useRuns } from "../context/RunContext";
import { formatTime } from "../lib/format";

export default function Results() {
  const { active, runs, setActiveId } = useRuns();

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 md:px-8 md:py-8">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#A879E5]">Outputs</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-indigo">Pipeline Results</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
            Open one agent at a time. Formatted sections and the original JSON come from that run’s saved files.
          </p>
        </div>
        {runs.length > 0 && (
          <label className="text-sm text-muted">
            Run
            <select
              value={active?.run_id || ""}
              onChange={(event) => setActiveId(event.target.value)}
              className="mt-1 block w-full rounded-xl border border-[#E9DDFB] bg-white px-3 py-2 text-sm font-semibold text-indigo outline-none focus:ring-2 focus:ring-[#7540C5] md:w-72 min-h-[44px]"
            >
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.filename} · {formatTime(run.started_at)}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>
      {!active && (
        <section className="glass px-6 py-10 text-center">
          <h2 className="text-lg font-bold text-indigo">No run selected</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            Start a pipeline from the dashboard, or reopen a completed run from history.
          </p>
          <div className="mt-4 flex justify-center gap-4 text-sm font-semibold text-[#7540C5]">
            <Link to="/">Dashboard</Link>
            <Link to="/history">Run History</Link>
          </div>
        </section>
      )}
      {active && (
        <>
          <RunSummary run={active} />
          <AgentBoard run={active} />
        </>
      )}
    </div>
  );
}
