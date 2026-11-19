import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Loader2,
  MinusCircle,
  SkipForward,
} from "lucide-react";

const STYLES = {
  pending:       { pill: "bg-[#E9DDFB] text-[#4A3566]",   Icon: Circle,        spin: false },
  running:       { pill: "bg-[#EDE8FA] text-[#7540C5]",   Icon: Loader2,       spin: true  },
  completed:     { pill: "bg-[#D1FAE5] text-[#065F46]",   Icon: CheckCircle2,  spin: false },
  failed:        { pill: "bg-[#FDECEC] text-[#B42318]",   Icon: AlertCircle,   spin: false },
  blocked:       { pill: "bg-[#FFF6E8] text-[#9A6700]",   Icon: AlertCircle,   spin: false },
  skipped:       { pill: "bg-[#FFF6E8] text-[#9A6700]",   Icon: SkipForward,   spin: false },
  warnings:      { pill: "bg-[#FFF6E8] text-[#9A6700]",   Icon: AlertCircle,   spin: false },
  passed:        { pill: "bg-[#D1FAE5] text-[#065F46]",   Icon: CheckCircle2,  spin: false },
  not_run:       { pill: "bg-[#E9DDFB] text-[#4A3566]",   Icon: MinusCircle,   spin: false },
  not_attempted: { pill: "bg-[#E9DDFB] text-[#4A3566]",   Icon: MinusCircle,   spin: false },
};

const DEFAULT_STYLE = { pill: "bg-[#E9DDFB] text-[#4A3566]", Icon: Circle, spin: false };

export default function StatusBadge({ status = "pending" }) {
  const value      = typeof status === "string" ? status : "pending";
  const normalized = value.toLowerCase().replaceAll(" ", "_");
  const label      = normalized
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
  const { pill, Icon, spin } = STYLES[normalized] || DEFAULT_STYLE;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${pill}`}>
      <Icon size={12} className={spin ? "animate-spin" : ""} aria-hidden="true" />
      {label}
    </span>
  );
}
