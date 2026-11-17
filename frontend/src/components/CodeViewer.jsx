import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";
import { highlightPseudocode } from "../lib/highlight";

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
  lineNum: {
    color: "var(--mute, #7d8aa3)",
    opacity: 0.6,
    userSelect: "none",
    paddingLeft: 12,
    paddingRight: 12,
    textAlign: "right",
    width: 44,
    borderRight: "1px solid rgba(36, 48, 68, 0.5)",
  },
  lineCell: {
    color: "#9fb3d1",
    paddingLeft: 12,
    paddingRight: 12,
    whiteSpace: "pre-wrap",
  },
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
        <div className="text-sm font-semibold font-mono" style={{ color: "var(--text, #d6deeb)" }}>
          {title}
        </div>
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
              <tr key={`${index}-${line}`} className="align-top hover:bg-[rgba(125,211,252,0.02)]">
                <td style={dark.lineNum}>{index + 1}</td>
                <td
                  style={dark.lineCell}
                  dangerouslySetInnerHTML={{ __html: highlightPseudocode(String(line)) || "&nbsp;" }}
                />
              </tr>
            ))}
          </tbody>
        </table>
        {!lines?.length && (
          <p className="px-4 py-6 text-sm" style={{ color: "var(--mute, #7d8aa3)" }}>
            No pseudocode was recorded.
          </p>
        )}
      </div>
    </div>
  );
}
