import { CloudUpload, FileText, Loader2, Square, X } from "lucide-react";
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
  const { startRun, cancelRun, running } = useRuns();
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

  /* Drop zone styling matching reference dark theme */
  const zoneClass = [
    "mt-4 flex w-full flex-col items-center rounded-xl border-2 border-dashed",
    "px-4 py-8 text-center transition cursor-pointer",
    running
      ? "cursor-not-allowed border-[var(--line)] bg-[rgba(10,14,20,0.2)] opacity-50"
      : dragOver
        ? "border-[var(--acc)] bg-[rgba(125,211,252,0.08)] scale-[1.005]"
        : "border-[#3b4c6b] bg-[rgba(10,14,20,0.4)] hover:border-[var(--acc)] hover:bg-[rgba(125,211,252,0.04)]",
  ].join(" ");

  return (
    <div>
      {/* Title */}
      <h2 className="text-xl font-bold font-mono tracking-tight text-[var(--text)]">Upload Hardware Specification</h2>
      <p className="mt-1 text-xs text-[var(--mute)]">PDF or DOCX (≤ 20 MB) · Automatic extraction & Verilog synthesis</p>

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
        <span className="grid h-12 w-12 place-items-center rounded-xl bg-[rgba(125,211,252,0.1)] p-3 text-[var(--acc)]">
          <CloudUpload size={24} />
        </span>
        <span className="mt-3 text-sm font-semibold text-[var(--text)]">
          {dragOver ? "Drop to upload" : "Drag a specification here"}
        </span>
        <span className="mt-1 text-xs text-[var(--mute)]">or click Browse Files below</span>
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
        <div className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.7)] px-4 py-3 backdrop-blur">
          <div className="flex min-w-0 items-center gap-3">
            <FileText className="shrink-0 text-[var(--acc)]" size={18} />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold font-mono text-[var(--text)]">{file.name}</div>
              <div className="text-xs text-[var(--mute)]">{fileKind(file)} · {formatBytes(file.size)}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setFile(null)}
            className="rounded-lg p-1.5 text-[var(--mute)] hover:text-[var(--bad)] hover:bg-[rgba(248,113,113,0.1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)]"
            aria-label="Remove selected file"
            disabled={running}
            style={{ minHeight: 44, minWidth: 44, display: "flex", alignItems: "center", justifyContent: "center" }}
          >
            <X size={15} />
          </button>
        </div>
      )}

      {/* Error message */}
      {message && (
        <p className="mt-3 rounded-lg border border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.1)] p-3 text-xs font-mono text-[var(--bad)]">
          {message}
        </p>
      )}

      {/* Action buttons */}
      <div className="mt-5 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        {/* Browse Files — ghost button */}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={running}
          className="w-full sm:w-auto min-h-[42px] flex items-center justify-center rounded-lg border border-[var(--line)] bg-transparent px-5 py-2 text-xs font-bold font-mono text-[var(--text)] transition hover:border-[var(--acc)] hover:text-[var(--acc)] hover:bg-[rgba(125,211,252,0.06)] disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)]"
        >
          Browse Files
        </button>

        {/* Run Pipeline — primary gradient accent */}
        <button
          type="button"
          onClick={submit}
          disabled={!file || running}
          title={!file ? "Select a specification file first" : undefined}
          className="w-full sm:w-auto min-h-[42px] inline-flex items-center justify-center gap-2 rounded-lg px-6 py-2 text-xs font-bold font-mono transition disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)]"
          style={
            !file || running
              ? {
                  background: "rgba(36, 48, 68, 0.35)",
                  color: "var(--mute, #7d8aa3)",
                  border: "1px dashed var(--line, #243044)",
                  cursor: "not-allowed",
                }
              : {
                  background: "linear-gradient(135deg, var(--acc2, #a78bfa), #6366f1)",
                  color: "#ffffff",
                  border: "1px solid transparent",
                  boxShadow: "0 4px 14px rgba(167, 139, 250, 0.35)",
                }
          }
        >
          {running
            ? <><Loader2 size={14} className="animate-spin" aria-hidden="true" />Pipeline running…</>
            : "Run Pipeline ▶"}
        </button>

        {running && (
          <button
            type="button"
            onClick={() => cancelRun()}
            className="w-full sm:w-auto min-h-[42px] inline-flex items-center justify-center gap-2 rounded-lg border border-[rgba(248,113,113,0.4)] bg-[rgba(248,113,113,0.15)] px-5 py-2 text-xs font-bold font-mono text-[var(--bad)] hover:bg-[rgba(248,113,113,0.25)] hover:border-[var(--bad)] transition shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bad)]"
            title="Immediately cancel this active pipeline run"
          >
            <Square size={12} className="fill-[var(--bad)]" />
            Stop Pipeline
          </button>
        )}
      </div>
    </div>
  );
}
