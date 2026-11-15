import { Cpu, FileEdit, History, LayoutDashboard, PanelsTopLeft, Settings, X } from "lucide-react";
import { NavLink } from "react-router-dom";

const LINKS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/results", label: "Pipeline Results", icon: PanelsTopLeft },
  { to: "/history", label: "Run History", icon: History },
  { to: "/composer", label: "Composer", icon: FileEdit },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar({ open, onClose }) {
  return (
    <>
      {open && (
        <button
          className="fixed inset-0 z-30 bg-[#35145D]/20 md:hidden"
          onClick={onClose}
          aria-label="Close navigation"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r transition-transform md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center justify-between px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="relative grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-[#7540C5] text-white shadow-glow">
              <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-[#C8F52F]" />
              <Cpu size={18} />
            </div>
            <div>
              <div className="text-sm font-bold tracking-tight text-indigo">SPEC2RTL</div>
              <div className="text-[10px] text-muted">Spec-to-RTL Pipeline</div>
            </div>
          </div>
          <button
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-muted md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5]"
            onClick={onClose}
            aria-label="Close menu"
          >
            <X size={16} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex flex-1 flex-col gap-1 px-3">
          {LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex min-h-[44px] items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5] ${
                    isActive
                      ? "bg-[#7540C5] text-white shadow-glow"
                      : "text-[#4A3566] hover:bg-[#E9DDFB]/60"
                  }`
                }
              >
                <Icon size={17} />
                {link.label}
              </NavLink>
            );
          })}
        </nav>

        {/* Footer badge */}
        <div className="m-4 rounded-2xl bg-[#F8F5FF]/80 px-4 py-3 text-[11px] leading-5 text-muted border border-[#E9DDFB]/60">
          <span className="font-semibold text-[#7540C5]">v1.0</span> · 7-stage multi-agent pipeline
        </div>
      </aside>
    </>
  );
}
