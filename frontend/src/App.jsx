import { Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import BinaryBackground from "./components/BinaryBackground";
import Sidebar from "./components/Sidebar";
import { useAuth } from "./context/AuthContext";
import { useRuns } from "./context/RunContext";
import Composer from "./pages/Composer";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Login from "./pages/Login";
import Results from "./pages/Results";
import Settings from "./pages/Settings";

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { banner, setBanner } = useRuns();
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  // Dynamic document title based on current page
  useEffect(() => {
    if (!isAuthenticated) return;
    const titles = {
      "/": "Dashboard · SPEC2RTL",
      "/results": "Pipeline Results · SPEC2RTL",
      "/history": "Run History · SPEC2RTL",
      "/composer": "Composer · SPEC2RTL",
      "/settings": "Settings · SPEC2RTL",
    };
    document.title = titles[location.pathname] || "SPEC2RTL";
  }, [isAuthenticated, location.pathname]);

  // Initial authentication check
  if (loading) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-[#060814] text-[var(--acc)] font-mono text-xs select-none">
        <span className="animate-pulse tracking-[0.2em] uppercase font-bold">&gt; INITIALIZING SPEC2RTL…</span>
      </div>
    );
  }

  // Gate the entire application: Show creative login page when not authenticated
  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <>
      {/* Canvas sits at z-index 0 (position:fixed), behind everything */}
      <BinaryBackground />

      {/* App shell at z-index 1, above the canvas */}
      <div className="s2r-app min-h-screen text-[var(--text)]">
        {/* Sidebar is position:fixed z-40 — well above canvas and app content */}
        <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
        <div className="md:pl-64">
          {/* Mobile top bar: sticky z-20 — matches reference header */}
          <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-[var(--line)] bg-[rgba(10,14,20,0.85)] px-4 py-3 backdrop-blur md:hidden font-mono font-bold tracking-wide">
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-[var(--text)] hover:text-[var(--acc)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acc)]"
              aria-label="Open navigation"
            >
              <Menu size={18} />
            </button>
            <span><span className="text-[var(--acc)]">&gt;</span> SPEC2RTL</span>
          </header>
          {banner && (
            <div className="mx-auto max-w-6xl px-4 pt-4 md:px-8">
              <div className="flex items-start justify-between gap-3 rounded-2xl border border-[rgba(248,113,113,0.4)] bg-[rgba(248,113,113,0.08)] px-4 py-3 text-sm text-[#fca5a5] font-mono">
                <p>{banner}</p>
                <button type="button" onClick={() => setBanner(null)} className="font-semibold text-[var(--bad)] hover:underline">
                  Dismiss
                </button>
              </div>
            </div>
          )}
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/results" element={<Results />} />
            <Route path="/history" element={<History />} />
            <Route path="/composer" element={<Composer />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </>
  );
}
