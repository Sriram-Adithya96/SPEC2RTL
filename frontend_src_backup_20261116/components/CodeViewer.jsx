import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";
import { highlightPseudocode } from "../lib/highlight";

/* Dark surface shared styles (same palette as JsonViewer) */
const dark = {
  wrap:    { background: "#1E0B38", border: "1px solid rgba(197,166,242,0.18)", borderRadius: 16, overflow: "hidden" },
  header:  { background: "rgba(255,255,255,0.05)", borderBottom: "1px solid rgba(197,166,242,0.12)" },
  btnCopy: "inline-flex items-center gap-1.5 rounded-lg border border-[#C5A6F2]/30 px-2.5 py-1.5 text-xs font-semibold text-[#C5A6F2] hover:bg-white/10 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5]",
  btnDl:   "inline-flex items-center gap-1.5 rounded-lg bg-[#7540C5]/80 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-[#7540C5] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C8F52F]",
  lineNum: { color: "#6B4E9E", userSelect: "none", paddingLeft: 12, paddingRight: 12, textAlign: "right", width: 44 },
  lineCell:{ color: "#E9DEFF", paddingLeft: 12, paddingRight: 12, whiteSpace: "pre-wrap" },
};

export default function CodeViewer({ lines, title, downloadName }) {
  const [copied, setCopied] = useState(false);
  const source = (lines || []).join("\n");

  async function copy() {
    await navigator.clipboard.writeText(source);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  function download() {
    const blob = new Blob([source], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = downloadName || "pseudocode.txt";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div style={dark.wrap}>
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 py-3" style={dark.header}>
        <div className="text-sm font-semibold" style={{ color: "#C5A6F2" }}>{title}</div>
        <div className="flex gap-2">
          <button onClick={copy} className={dark.btnCopy}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy"}
          </button>
          <button onClick={download} className={dark.btnDl}>
            <Download size={14} />
            Download
          </button>
        </div>
      </div>

      {/* Line-numbered code body */}
      <div className="max-h-[34rem] overflow-auto">
        <table
          className="w-full border-collapse text-xs leading-6"
          style={{ fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace" }}
        >
          <tbody>
            {(lines || []).map((line, index) => (
              <tr key={`${index}-${line}`} className="align-top">
                <td style={dark.lineNum}>{index + 1}</td>
                <td
                  style={dark.lineCell}
                  dangerouslySetInnerHTML={{ __html: highlightPseudocodeDark(String(line)) || "&nbsp;" }}
                />
              </tr>
            ))}
          </tbody>
        </table>
        {!lines?.length && (
          <p className="px-4 py-6 text-sm" style={{ color: "#A879E5" }}>No pseudocode was recorded.</p>
        )}
      </div>
    </div>
  );
}

/**
 * Re-maps pseudocode keyword highlights to dark-surface colours.
 * Keyword logic and stored data are unchanged.
 */
function highlightPseudocodeDark(line) {
  function escapeHtml(v) {
    return v.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  }
  const PSEUDO_KEYWORDS =
    /\b(MODULE|END MODULE|INPUT|OUTPUT|INOUT|CLOCK|EDGE|RISING|FALLING|REG|SIG|PARAMETER|CONST|STATE|BLOCK|COMBINATIONAL|CLOCKED|END BLOCK|IF|ELSE|END IF|CASE|WHEN|END CASE|ASSIGN|RESET|END RESET|FUNCTION|END FUNCTION|UNRESOLVED)\b/g;
  return escapeHtml(line).replace(
    PSEUDO_KEYWORDS,
    '<span style="color:#C5A6F2;font-weight:600">$1</span>',
  );
}
