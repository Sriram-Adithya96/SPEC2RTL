import { asText } from "../lib/format";

export default function SignalTable({ signals }) {
  if (!Array.isArray(signals) || signals.length === 0) {
    return <p className="text-sm text-muted">No signals recorded.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[#E9DDFB]">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-[#F8F5FF] text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="px-3 py-2 font-semibold">Name</th>
            <th className="px-3 py-2 font-semibold">Direction</th>
            <th className="px-3 py-2 font-semibold">Width</th>
            <th className="px-3 py-2 font-semibold">Description</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((signal, index) => (
            <tr key={`${signal?.name || "signal"}-${index}`} className="border-t border-[#E9DDFB]">
              <td className="px-3 py-2 font-semibold text-indigo">{asText(signal?.name, "Unnamed")}</td>
              <td className="px-3 py-2 text-[#4A3566]">{asText(signal?.direction, "—")}</td>
              <td className="px-3 py-2 text-[#4A3566]">{asText(signal?.width, "—")}</td>
              <td className="px-3 py-2 text-[#4A3566]">{asText(signal?.description, "—")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
