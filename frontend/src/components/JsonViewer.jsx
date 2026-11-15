import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";
import { highlightJson } from "../lib/highlight";

const PREVIEW_LIMIT = 300000;

/* Dark surface shared styles */
const dark = {
  wrap:    { background: "#1E0B38", border: "1px solid rgba(197,166,242,0.18)", borderRadius: 16, overflow: "hidden" },
  header:  { background: "rgba(255,255,255,0.05)", borderBottom: "1px solid rgba(197,166,242,0.12)" },
  btnCopy: "inline-flex items-center gap-1.5 rounded-lg border border-[#C5A6F2]/30 px-2.5 py-1.5 text-xs font-semibold text-[#C5A6F2] hover:bg-white/10 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5]",
  btnDl:   "inline-flex items-center gap-1.5 rounded-lg bg-[#7540C5]/80 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-[#7540C5] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C8F52F]",
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
        <div className="text-sm font-semibold" style={{ color: "#C5A6F2" }}>{filename}</div>
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
        <p className="px-4 py-2 text-xs" style={{ color: "#A879E5", borderBottom: "1px solid rgba(197,166,242,0.12)", background: "rgba(255,255,255,0.03)" }}>
          Showing the first portion of a large file. Download it to read the full JSON.
        </p>
      )}

      {/* Code body — JetBrains Mono, light text on dark surface */}
      <pre
        className="max-h-[32rem] overflow-auto px-4 py-4 text-xs leading-6"
        style={{ fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace", color: "#E9DEFF", margin: 0 }}
        dangerouslySetInnerHTML={{ __html: highlightJsonDark(visible) }}
      />
    </div>
  );
}

/**
 * Re-maps the existing highlightJson colours to dark-surface-friendly values.
 * Keys → bright lavender, strings → soft lilac, booleans/null → teal/muted.
 * No changes to the underlying highlight logic or stored data.
 */
function highlightJsonDark(text) {
  function escapeHtml(v) {
    return v.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  }
  const source = escapeHtml(text);
  return source.replace(
    /("(?:\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(\s*:)?|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      let style;
      if (match.startsWith('"')) {
        style = match.trimEnd().endsWith(":")
          ? "color:#E9DEFF;font-weight:600"      // key
          : "color:#C5A6F2";                     // string value
      } else if (match === "true" || match === "false") {
        style = "color:#6EE7B7";                 // boolean — soft teal
      } else if (match === "null") {
        style = "color:#A879E5";                 // null — muted purple
      } else {
        style = "color:#DCCBFA";                 // number
      }
      return `<span style="${style}">${match}</span>`;
    },
  );
}
