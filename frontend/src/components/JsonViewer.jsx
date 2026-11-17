import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";
import { highlightJson } from "../lib/highlight";

const PREVIEW_LIMIT = 300000;

/* Dark code-editor styles matching reference dark theme */
const dark = {
  wrap: {
    background: "#05080d",
    border: "1px solid var(--line, #243044)",
    borderRadius: 12,
    overflow: "hidden",
  },
  header: {
    background: "rgba(16, 22, 32, 0.85)",
    borderBottom: "1px solid var(--line, #243044)",
  },
  btnCopy:
    "inline-flex items-center gap-1.5 rounded-lg border border-[var(--line,#243044)] bg-transparent px-2.5 py-1.5 text-xs font-semibold text-[var(--mute,#7d8aa3)] hover:text-[var(--text,#d6deeb)] hover:border-[var(--acc,#7dd3fc)] hover:bg-[rgba(125,211,252,0.08)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc,#7dd3fc)]",
  btnDl:
    "inline-flex items-center gap-1.5 rounded-lg border border-[var(--acc2,#a78bfa)]/50 bg-[rgba(167,139,250,0.15)] px-2.5 py-1.5 text-xs font-semibold text-[var(--acc2,#a78bfa)] hover:bg-[rgba(167,139,250,0.25)] hover:text-white transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc2,#a78bfa)]",
};

export default function JsonViewer({ raw, filename, downloadHref }) {
  const [copied, setCopied] = useState(false);
  const text = raw || "";
  const truncated = text.length > PREVIEW_LIMIT;
  const visible = truncated ? text.slice(0, PREVIEW_LIMIT) : text;

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div style={dark.wrap}>
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 py-3" style={dark.header}>
        <div className="text-sm font-semibold font-mono" style={{ color: "var(--text, #d6deeb)" }}>
          {filename}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={copy} className={dark.btnCopy}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy"}
          </button>
          {downloadHref && (
            <a href={downloadHref} className={dark.btnDl}>
              <Download size={14} />
              Download
            </a>
          )}
        </div>
      </div>

      {/* Truncation notice */}
      {truncated && (
        <p
          className="px-4 py-2 text-xs font-mono"
          style={{
            color: "var(--mute, #7d8aa3)",
            borderBottom: "1px solid var(--line, #243044)",
            background: "rgba(16, 22, 32, 0.6)",
          }}
        >
          Showing the first portion of a large file. Download it to read the full JSON.
        </p>
      )}

      {/* Code body — JetBrains Mono, high-contrast dark surface */}
      <pre
        className="max-h-[32rem] overflow-auto px-4 py-4 text-xs leading-6"
        style={{
          fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace",
          color: "#9fb3d1",
          margin: 0,
        }}
        dangerouslySetInnerHTML={{ __html: highlightJson(visible) }}
      />
    </div>
  );
}
