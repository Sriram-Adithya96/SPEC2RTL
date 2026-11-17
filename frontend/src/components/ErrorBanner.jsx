import { useState } from "react";

/** Detect a 13-digit ms epoch in [2020-01-01, 2030-01-01] and format as local time. */
function fmtMsTimestamp(raw) {
  const m = raw.match(/\b(1[5-9]\d{11})\b/);
  if (!m) return null;
  const n = parseInt(m[1], 10);
  try {
    return new Date(n).toLocaleString();
  } catch {
    return null;
  }
}

/**
 * Parse error string into unique messages with counts.
 * Input: messages separated by "; " (may repeat).
 * Output: [{ msg, count }] sorted by first appearance.
 */
function parseError(error) {
  if (!error) return [];
  const parts = error.split(/;\s+/);
  const seen = new Map();
  for (const p of parts) {
    const t = p.trim();
    if (!t) continue;
    seen.set(t, (seen.get(t) || 0) + 1);
  }
  return Array.from(seen.entries()).map(([msg, count]) => ({ msg, count }));
}

/** Display-only error banner with dedup + raw toggle. */
export default function ErrorBanner({ error, title, className = "" }) {
  const [showRaw, setShowRaw] = useState(false);
  if (!error) return null;

  const parsed = parseError(error);
  const isDeduped =
    parsed.length > 0 &&
    (parsed.length < error.split(/;\s+/).filter(Boolean).length ||
      parsed.some((p) => p.count > 1));
  const ts = fmtMsTimestamp(error);

  return (
    <div
      className={`rounded-xl border border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.08)] px-4 py-3 text-xs font-mono text-[var(--bad)] ${className}`}
    >
      {title && <div className="mb-1 font-bold">{title}</div>}

      {/* Deduplicated view */}
      {!showRaw && (
        <ul className="space-y-1">
          {parsed.map(({ msg, count }, i) => (
            <li key={i} className="flex items-start gap-2 leading-snug">
              <span className="flex-1">{msg}</span>
              {count > 1 && (
                <span className="shrink-0 rounded-full bg-[rgba(248,113,113,0.2)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--bad)]">
                  ×{count}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Raw text */}
      {showRaw && (
        <p className="whitespace-pre-wrap break-words text-xs leading-5">
          {error}
        </p>
      )}

      {/* Rate-limit human timestamp */}
      {ts && !showRaw && (
        <p className="mt-1.5 text-[11px] opacity-80">Reset at: {ts}</p>
      )}

      {/* Toggle */}
      {isDeduped && (
        <button
          type="button"
          onClick={() => setShowRaw((r) => !r)}
          className="mt-2 text-xs font-semibold underline underline-offset-2 hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bad)]"
        >
          {showRaw ? "Show summary" : "Show raw error"}
        </button>
      )}
    </div>
  );
}
