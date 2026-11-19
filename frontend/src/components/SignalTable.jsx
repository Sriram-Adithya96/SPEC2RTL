import { asText } from "../lib/format";

export default function SignalTable({ signals }) {
  if (!Array.isArray(signals) || signals.length === 0) {
    return <p className="text-xs font-mono text-[var(--mute)]">No signals recorded.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--line)] bg-[rgba(10,14,20,0.4)]">
      <table className="min-w-full text-left text-xs font-mono">
        <thead className="bg-[rgba(16,22,32,0.85)] text-[10px] uppercase tracking-wider text-[var(--mute)]">
          <tr>
            <th className="px-3.5 py-2.5 font-bold">Name</th>
            <th className="px-3.5 py-2.5 font-bold">Direction</th>
            <th className="px-3.5 py-2.5 font-bold">Width</th>
            <th className="px-3.5 py-2.5 font-bold">Description</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--line)]">
          {signals.map((signal, index) => (
            <tr key={`${signal?.name || "signal"}-${index}`} className="hover:bg-[rgba(125,211,252,0.03)] transition">
              <td className="px-3.5 py-2.5 font-bold text-[var(--acc)]">{asText(signal?.name, "Unnamed")}</td>
              <td className="px-3.5 py-2.5 text-[var(--text)]">{asText(signal?.direction, "—")}</td>
              <td className="px-3.5 py-2.5 text-[var(--text)]">{asText(signal?.width, "—")}</td>
              <td className="px-3.5 py-2.5 text-[var(--mute)]">{asText(signal?.description, "—")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
