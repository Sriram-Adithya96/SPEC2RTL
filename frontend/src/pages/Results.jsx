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
          <p className="font-mono text-xs font-bold uppercase tracking-[0.16em] text-[var(--acc2)]">Outputs</p>
          <h1 className="mt-1 font-mono text-2xl md:text-3xl font-extrabold tracking-tight text-[var(--text)]">Pipeline Results</h1>
          <p className="mt-2 max-w-2xl text-xs text-[var(--mute)]">
            Open one agent at a time. Formatted sections and the original JSON come from that run's saved files.
          </p>
        </div>
        {runs.length > 0 && (
          <label className="font-mono text-xs text-[var(--mute)]">
            Run
            <select
              value={active?.run_id || ""}
              onChange={(event) => setActiveId(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.8)] px-3 py-2 font-mono text-xs font-semibold text-[var(--text)] outline-none focus:ring-2 focus:ring-[var(--acc)] md:w-72 min-h-[38px]"
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
          <h2 className="font-mono text-lg font-bold text-[var(--text)]">No run selected</h2>
          <p className="mx-auto mt-2 max-w-md text-xs text-[var(--mute)]">
            Start a pipeline from the dashboard, or reopen a completed run from history.
          </p>
          <div className="mt-4 flex justify-center gap-6 font-mono text-xs font-semibold text-[var(--acc)]">
            <Link to="/" className="hover:underline">Dashboard</Link>
            <Link to="/history" className="hover:underline">Run History</Link>
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
