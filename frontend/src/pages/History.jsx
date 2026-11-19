import { Download, FolderOpen } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ErrorBanner from "../components/ErrorBanner";
import StatusBadge from "../components/StatusBadge";
import { api, apiUrl, errorMessage } from "../api";
import { useRuns } from "../context/RunContext";
import { formatBytes, formatTime, formatTokensCompact } from "../lib/format";

export default function History() {
  const { runs, setActiveId, refreshRuns } = useRuns();
  const navigate = useNavigate();
  const [files, setFiles] = useState({});
  const [openId, setOpenId] = useState(null);
  const [loadingId, setLoadingId] = useState(null);
  const [message, setMessage] = useState("");

  async function showFiles(runId) {
    if (openId === runId) {
      setOpenId(null);
      return;
    }
    setOpenId(runId);
    if (files[runId]) return;
    setLoadingId(runId);
    try {
      const response = await api.get(`/runs/${runId}/outputs`);
      setFiles((current) => ({ ...current, [runId]: response.data.files || [] }));
    } catch (error) {
      setMessage(errorMessage(error, "Could not list output files."));
    } finally {
      setLoadingId(null);
    }
  }

  function reopen(runId) {
    setActiveId(runId);
    navigate("/results");
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 md:px-8 md:py-8">
      <header className="flex items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs font-bold uppercase tracking-[0.16em] text-[var(--acc2)]">Archive</p>
          <h1 className="mt-1 font-mono text-2xl md:text-3xl font-extrabold tracking-tight text-[var(--text)]">Run History</h1>
          <p className="mt-2 text-xs text-[var(--mute)]">Each execution keeps its own output directory.</p>
        </div>
        <button
          type="button"
          onClick={() => refreshRuns().catch((error) => setMessage(errorMessage(error, "Could not refresh history.")))}
          className="min-h-[40px] rounded-lg border border-[var(--line)] bg-transparent px-4 py-2 font-mono text-xs font-semibold text-[var(--text)] transition hover:border-[var(--acc)] hover:text-[var(--acc)] hover:bg-[rgba(125,211,252,0.06)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)]"
        >
          Refresh
        </button>
      </header>
      {message && (
        <p className="rounded-lg border border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.08)] px-3 py-2 font-mono text-xs text-[var(--bad)]">
          {message}
        </p>
      )}
      {runs.length === 0 && (
        <section className="glass px-6 py-10 text-center">
          <h2 className="font-mono text-lg font-bold text-[var(--text)]">No pipeline runs yet</h2>
          <p className="mt-2 text-xs text-[var(--mute)]">Completed and failed executions will be listed here.</p>
        </section>
      )}
      <div className="grid gap-3">
        {runs.map((run) => (
          <article key={run.run_id} className="glass p-4 md:p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate font-mono font-bold text-[var(--text)]">{run.filename}</h2>
                  <StatusBadge status={run.status} />
                </div>
                <p className="mt-1 font-mono text-xs text-[var(--mute)]">
                  {formatTime(run.started_at)}
                  {run.file_type ? ` · ${run.file_type.replace(".", "").toUpperCase()}` : ""}
                  {Number.isFinite(run.file_size) ? ` · ${formatBytes(run.file_size)}` : ""}
                  {run.source === "cli" ? " · CLI run" : ""}
                  {run.token_usage?.total_tokens > 0 ? ` · ⚡ ${formatTokensCompact(run.token_usage.total_tokens)} tokens` : ""}
                </p>
                {run.error && (
                  <div className="mt-2">
                    <ErrorBanner error={run.error} />
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => reopen(run.run_id)}
                  className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border border-[var(--acc2)]/50 bg-[rgba(167,139,250,0.15)] px-4 py-2 font-mono text-xs font-semibold text-[var(--acc2)] transition hover:bg-[rgba(167,139,250,0.28)] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc2)]"
                >
                  <FolderOpen size={14} />
                  Open
                </button>
                <button
                  type="button"
                  onClick={() => showFiles(run.run_id)}
                  className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border border-[var(--line)] bg-transparent px-4 py-2 font-mono text-xs font-semibold text-[var(--mute)] transition hover:border-[var(--acc)] hover:text-[var(--acc)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)]"
                >
                  <Download size={14} />
                  Outputs
                </button>
              </div>
            </div>
            {openId === run.run_id && (
              <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--line)] pt-4">
                {loadingId === run.run_id && <p className="font-mono text-xs text-[var(--mute)]">Loading output files…</p>}
                {loadingId !== run.run_id && (files[run.run_id] || []).length === 0 && (
                  <p className="font-mono text-xs text-[var(--mute)]">No output files saved for this run.</p>
                )}
                {(files[run.run_id] || []).map((filename) => (
                  <a
                    key={filename}
                    href={apiUrl(`/runs/${run.run_id}/download/${filename}`)}
                    className="rounded-md border border-[var(--line)] bg-[rgba(36,48,68,0.5)] px-2.5 py-1 font-mono text-xs font-semibold text-[var(--acc)] hover:border-[var(--acc)] hover:text-[var(--text)] transition"
                  >
                    {filename}
                  </a>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
