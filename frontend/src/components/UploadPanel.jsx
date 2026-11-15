import { CloudUpload, FileText, Loader2, X } from "lucide-react";
import { useRef, useState } from "react";
import { useRuns } from "../context/RunContext";
import { formatBytes } from "../lib/format";

const MAX_BYTES = 20 * 1024 * 1024;

function fileKind(file) {
  const name = file.name.toLowerCase();
  if (name.endsWith(".pdf")) return "PDF";
  if (name.endsWith(".docx")) return "DOCX";
  return "File";
}

export default function UploadPanel() {
  const { startRun, running } = useRuns();
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState("");
  const [dragOver, setDragOver] = useState(false);

  function choose(next) {
    if (!next) return;
    const name = next.name.toLowerCase();
    if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
      setFile(null);
      setMessage("Upload a PDF or DOCX hardware specification.");
      return;
    }
    if (next.size === 0) {
      setFile(null);
      setMessage("The selected file is empty.");
      return;
    }
    if (next.size > MAX_BYTES) {
      setFile(null);
      setMessage("File exceeds the 20 MB limit.");
      return;
    }
    setFile(next);
    setMessage("");
  }

  async function submit() {
    if (!file || running) return;
    try {
      await startRun(file);
    } catch (error) {
      setMessage(error.message || "The pipeline could not be started.");
    }
  }

  /* Drop zone class: normal / drag-over / running-locked */
  const zoneClass = [
    "mt-4 flex w-full flex-col items-center rounded-2xl border-2 border-dashed",
    "px-4 py-8 text-center transition",
    running
      ? "cursor-not-allowed border-[#C5A6F2]/30 bg-[#F8F5FF]/30 opacity-60"
      : dragOver
        ? "border-[#7540C5] bg-[#C5A6F2]/25 scale-[1.01]"
        : "border-[#C5A6F2] bg-[rgba(220,203,250,0.28)] hover:border-[#A879E5] hover:bg-[#DCCBFA]/25",
  ].join(" ");

  return (
    <div>
      {/* Title */}
      <h2 className="text-xl font-bold tracking-tight text-indigo">Upload Hardware Specification</h2>
      <p className="mt-1 text-sm text-muted">PDF or DOCX (≤ 20 MB)</p>

      {/* Drop zone */}
      <button
        type="button"
        onClick={() => !running && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); if (!running) setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); if (!running) choose(e.dataTransfer.files?.[0]); }}
        disabled={running}
        aria-label="Drop zone — drag a specification here or click to browse"
        className={zoneClass}
        style={{ minHeight: 44 }}
      >
        <span className="grid h-13 w-13 place-items-center rounded-2xl bg-[#E9DDFB] p-3 text-[#7540C5]">
          <CloudUpload size={26} />
        </span>
        <span className="mt-3 text-sm font-semibold text-indigo">
          {dragOver ? "Drop to upload" : "Drag a specification here"}
        </span>
        <span className="mt-1 text-xs text-muted">or click Browse Files below</span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }}
      />

      {/* Selected file chip */}
      {file && (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-2xl border border-[#E9DDFB] bg-white/70 px-4 py-3 backdrop-blur">
          <div className="flex min-w-0 items-center gap-3">
            <FileText className="shrink-0 text-[#7540C5]" size={18} />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-indigo">{file.name}</div>
              <div className="text-xs text-muted">{fileKind(file)} · {formatBytes(file.size)}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setFile(null)}
            className="rounded-lg p-1.5 text-muted hover:bg-[#F8F5FF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5]"
            aria-label="Remove selected file"
            disabled={running}
            style={{ minHeight: 44, minWidth: 44, display: "flex", alignItems: "center", justifyContent: "center" }}
          >
            <X size={15} />
          </button>
        </div>
      )}

      {/* Error message */}
      {message && <p className="mt-3 text-sm text-[#8F1D1D]">{message}</p>}

      {/* Action buttons */}
      <div className="mt-5 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        {/* Browse Files — outlined purple */}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={running}
          className="w-full sm:w-auto min-h-[44px] flex items-center justify-center rounded-xl border-2 border-[#7540C5] px-5 py-2.5 text-sm font-semibold text-[#7540C5] transition hover:bg-[#7540C5] hover:text-white disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5] focus-visible:ring-offset-2"
        >
          Browse Files
        </button>

        {/* Run Pipeline — purple gradient + lime underline accent when active; clear high-contrast disabled state with dashed border */}
        <button
          type="button"
          onClick={submit}
          disabled={!file || running}
          title={!file ? "Select a specification file first" : undefined}
          className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 rounded-xl px-6 py-2.5 text-sm font-bold shadow-sm transition disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C8F52F] focus-visible:ring-offset-2"
          style={
            !file || running
              ? {
                  background: "#E9DDFB",
                  color: "#35145D",
                  border: "1.5px dashed #C5A6F2",
                  boxShadow: "none",
                  cursor: "not-allowed",
                }
              : {
                  background: "linear-gradient(135deg, #7540C5 0%, #35145D 100%)",
                  color: "#FFFFFF",
                  border: "1px solid transparent",
                  boxShadow: "0 2px 0 0 #C8F52F, 0 10px 28px rgba(117,64,197,0.32)",
                }
          }
        >
          {running
            ? <><Loader2 size={15} className="animate-spin" aria-hidden="true" />Pipeline running…</>
            : "Run Pipeline ▶"}
        </button>

        {running && (
          <span className="text-xs text-muted text-center sm:text-left">A pipeline run is in progress.</span>
        )}
      </div>
    </div>
  );
}
