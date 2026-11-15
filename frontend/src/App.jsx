import { Menu } from "lucide-react";
import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import ParticleBackground from "./ParticleBackground";
import Sidebar from "./components/Sidebar";
import { useRuns } from "./context/RunContext";
import Composer from "./pages/Composer";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Results from "./pages/Results";
import Settings from "./pages/Settings";

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { banner, setBanner } = useRuns();

  return (
    <>
      {/* Canvas sits at z-index 0 (position:fixed), behind everything */}
      <ParticleBackground />

      {/* App shell at z-index 1, above the canvas */}
      <div className="s2r-app min-h-screen">
        {/* Sidebar is position:fixed z-40 — well above canvas and app content */}
        <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
        <div className="md:pl-64">
          {/* Mobile top bar: sticky z-20 — above page content, below sidebar */}
          <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-[#E9DDFB]/80 bg-[#F8F5FF]/80 px-4 py-2 backdrop-blur md:hidden">
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-indigo focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7540C5]"
              aria-label="Open navigation"
            >
              <Menu size={18} />
            </button>
            <span className="font-bold text-indigo">SPEC2RTL</span>
          </header>
          {banner && (
            <div className="mx-auto max-w-6xl px-4 pt-4 md:px-8">
              <div className="flex items-start justify-between gap-3 rounded-2xl border border-[#F3C0C0] bg-[#FFF6F6] px-4 py-3 text-sm text-[#8F1D1D]">
                <p>{banner}</p>
                <button type="button" onClick={() => setBanner(null)} className="font-semibold">
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
