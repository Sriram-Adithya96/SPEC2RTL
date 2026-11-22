import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Loader2,
  MinusCircle,
  SkipForward,
} from "lucide-react";

const STYLES = {
  pending: {
    pill: "bg-[rgba(125,138,163,0.10)] text-[var(--mute)] border border-[rgba(125,138,163,0.25)]",
    Icon: Circle,
    spin: false,
  },
  running: {
    pill: "bg-[rgba(125,211,252,0.12)] text-[var(--acc)] border border-[rgba(125,211,252,0.35)]",
    Icon: Loader2,
    spin: true,
  },
  completed: {
    pill: "bg-[rgba(74,222,128,0.12)] text-[var(--ok)] border border-[rgba(74,222,128,0.35)]",
    Icon: CheckCircle2,
    spin: false,
  },
  failed: {
    pill: "bg-[rgba(248,113,113,0.12)] text-[var(--bad)] border border-[rgba(248,113,113,0.35)]",
    Icon: AlertCircle,
    spin: false,
  },
  cancelled: {
    pill: "bg-[rgba(248,113,113,0.12)] text-[var(--bad)] border border-[rgba(248,113,113,0.35)]",
    Icon: MinusCircle,
    spin: false,
  },
  blocked: {
    pill: "bg-[rgba(251,191,36,0.12)] text-[var(--warn)] border border-[rgba(251,191,36,0.35)]",
    Icon: AlertCircle,
    spin: false,
  },
  skipped: {
    pill: "bg-[rgba(251,191,36,0.12)] text-[var(--warn)] border border-[rgba(251,191,36,0.35)]",
    Icon: SkipForward,
    spin: false,
  },
  warnings: {
    pill: "bg-[rgba(251,191,36,0.12)] text-[var(--warn)] border border-[rgba(251,191,36,0.35)]",
    Icon: AlertCircle,
    spin: false,
  },
  passed: {
    pill: "bg-[rgba(74,222,128,0.12)] text-[var(--ok)] border border-[rgba(74,222,128,0.35)]",
    Icon: CheckCircle2,
    spin: false,
  },
  not_run: {
    pill: "bg-[rgba(125,138,163,0.10)] text-[var(--mute)] border border-[rgba(125,138,163,0.25)]",
    Icon: MinusCircle,
    spin: false,
  },
  not_attempted: {
    pill: "bg-[rgba(125,138,163,0.10)] text-[var(--mute)] border border-[rgba(125,138,163,0.25)]",
    Icon: MinusCircle,
    spin: false,
  },
};

const DEFAULT_STYLE = {
  pill: "bg-[rgba(125,138,163,0.10)] text-[var(--mute)] border border-[rgba(125,138,163,0.25)]",
  Icon: Circle,
  spin: false,
};

export default function StatusBadge({ status = "pending" }) {
  const value = typeof status === "string" ? status : "pending";
  const normalized = value.toLowerCase().replaceAll(" ", "_");
  const label = normalized
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
  const { pill, Icon, spin } = STYLES[normalized] || DEFAULT_STYLE;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-bold uppercase tracking-wider ${pill}`}
    >
      <Icon size={12} className={spin ? "animate-spin" : ""} aria-hidden="true" />
      {label}
    </span>
  );
}
