import { Download, FolderOpen } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ErrorBanner from "../components/ErrorBanner";
import StatusBadge from "../components/StatusBadge";
import { api, errorMessage } from "../api";
import { useRuns } from "../context/RunContext";
import { formatBytes, formatTime } from "../lib/format";

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
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#A879E5]">Archive</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-indigo">Run History</h1>
          <p className="mt-2 text-sm text-muted">Each execution keeps its own output directory.</p>
        </div>
        <button
          type="button"
          onClick={() => refreshRuns().catch((error) => setMessage(errorMessage(error, "Could not refresh history.")))}
          className="min-h-[44px] rounded-xl border border-[#E9DDFB] bg-white px-4 py-2 text-sm font-semibold text-[#4A3566] transition hover:bg-[#F8F5FF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5]"
        >
          Refresh
        </button>
      </header>
      {message && <p className="text-sm text-[#8F1D1D]">{message}</p>}
      {runs.length === 0 && (
        <section className="glass px-6 py-10 text-center">
          <h2 className="text-lg font-bold text-indigo">No pipeline runs yet</h2>
          <p className="mt-2 text-sm text-muted">Completed and failed executions will be listed here.</p>
        </section>
      )}
      <div className="grid gap-3">
        {runs.map((run) => (
          <article key={run.run_id} className="glass p-4 md:p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate font-bold text-indigo">{run.filename}</h2>
                  <StatusBadge status={run.status} />
                </div>
                <p className="mt-1 text-sm text-muted">
                  {formatTime(run.started_at)}
                  {run.file_type ? ` · ${run.file_type.replace(".", "").toUpperCase()}` : ""}
                  {Number.isFinite(run.file_size) ? ` · ${formatBytes(run.file_size)}` : ""}
                  {run.source === "cli" ? " · Command-line run" : ""}
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
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-xl bg-[#7540C5] px-4 py-2 text-sm font-semibold text-white shadow-glow transition hover:bg-[#35145D] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C8F52F]"
                >
                  <FolderOpen size={15} />
                  Open
                </button>
                <button
                  type="button"
                  onClick={() => showFiles(run.run_id)}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-xl border border-[#E9DDFB] bg-white px-4 py-2 text-sm font-semibold text-[#4A3566] transition hover:bg-[#F8F5FF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5]"
                >
                  <Download size={15} />
                  Outputs
                </button>
              </div>
            </div>
            {openId === run.run_id && (
              <div className="mt-4 flex flex-wrap gap-2 border-t border-[#E9DDFB] pt-4">
                {loadingId === run.run_id && <p className="text-sm text-muted">Loading output files.</p>}
                {loadingId !== run.run_id && (files[run.run_id] || []).length === 0 && (
                  <p className="text-sm text-muted">No output files saved for this run.</p>
                )}
                {(files[run.run_id] || []).map((filename) => (
                  <a
                    key={filename}
                    href={`/api/runs/${run.run_id}/download/${filename}`}
                    className="rounded-lg bg-[#E9DDFB] px-2.5 py-1.5 text-xs font-semibold text-[#4A3566]"
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
