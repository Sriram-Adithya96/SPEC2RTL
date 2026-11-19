import { Cpu, FileEdit, History, LayoutDashboard, LogIn, LogOut, PanelsTopLeft, Settings, User, X } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const LINKS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/results", label: "Pipeline Results", icon: PanelsTopLeft },
  { to: "/history", label: "Run History", icon: History },
  { to: "/composer", label: "Composer", icon: FileEdit },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar({ open, onClose }) {
  const { user, isAuthenticated, logout } = useAuth();
  return (
    <>
      {open && (
        <button
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-label="Close navigation"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-[var(--line)] bg-[rgba(10,14,20,0.92)] backdrop-blur-md transition-transform md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center justify-between px-5 py-5 border-b border-[var(--line)]/50">
          <div className="flex items-center gap-3">
            <div className="relative grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-[var(--acc2)] to-[var(--acc)] text-[#05080d] font-mono font-extrabold shadow-md">
              <Cpu size={18} />
            </div>
            <div>
              <div className="font-mono text-sm font-extrabold tracking-tight text-[var(--text)]">SPEC2RTL</div>
              <div className="font-mono text-[9px] uppercase tracking-wider text-[var(--mute)]">Spec &rarr; Verilog</div>
            </div>
          </div>
          <button
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-[var(--mute)] hover:text-[var(--text)] md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)]"
            onClick={onClose}
            aria-label="Close menu"
          >
            <X size={16} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex flex-1 flex-col gap-1.5 px-3 py-4">
          {LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex min-h-[42px] items-center gap-3 rounded-lg px-3 py-2 text-xs font-semibold font-mono tracking-wide transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)] ${
                    isActive
                      ? "border border-[var(--acc2)]/50 bg-[rgba(167,139,250,0.14)] text-[var(--text)] shadow-sm"
                      : "text-[var(--mute)] hover:text-[var(--text)] hover:bg-[rgba(36,48,68,0.45)] border border-transparent"
                  }`
                }
              >
                <Icon size={16} />
                {link.label}
              </NavLink>
            );
          })}
        </nav>

        {/* User Auth Section */}
        {isAuthenticated && user ? (
          <div className="mx-3 mb-2 rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.65)] p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="grid h-7 w-7 place-items-center rounded-lg bg-[rgba(125,211,252,0.15)] text-[var(--acc)] font-mono text-xs font-bold shrink-0">
                  {user.username ? user.username.charAt(0).toUpperCase() : "U"}
                </span>
                <div className="min-w-0">
                  <div className="truncate font-mono text-xs font-bold text-[var(--text)]">{user.username}</div>
                  <div className="truncate font-mono text-[10px] text-[var(--mute)]">{user.email}</div>
                </div>
              </div>
              <button
                type="button"
                onClick={logout}
                title="Sign Out"
                className="rounded-lg p-1.5 text-[var(--mute)] hover:text-[var(--bad)] hover:bg-[rgba(248,113,113,0.1)] transition shrink-0"
              >
                <LogOut size={14} />
              </button>
            </div>
          </div>
        ) : (
          <div className="mx-3 mb-2">
            <NavLink
              to="/login"
              onClick={onClose}
              className="flex items-center justify-center gap-2 rounded-xl border border-[var(--acc)]/40 bg-[rgba(125,211,252,0.08)] px-3 py-2.5 font-mono text-xs font-bold text-[var(--acc)] transition hover:bg-[rgba(125,211,252,0.15)]"
            >
              <LogIn size={14} />
              Sign In / Register
            </NavLink>
          </div>
        )}

        {/* Footer badge */}
        <div className="m-4 rounded-xl border border-[var(--line)] bg-[rgba(16,22,32,0.65)] px-3.5 py-3 text-[11px] font-mono leading-5 text-[var(--mute)]">
          <span className="font-bold text-[var(--acc)]">v1.0</span> · 7-stage multi-agent
        </div>
      </aside>
    </>
  );
}
