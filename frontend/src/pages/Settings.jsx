import { Cpu, ExternalLink, Settings2 } from "lucide-react";

const AGENTS = [
  { n: "01", name: "Understanding Agent", desc: "Parses and understands the hardware specification." },
  { n: "02", name: "Decomposer Agent", desc: "Breaks specification into hierarchical components." },
  { n: "03", name: "Description Agent", desc: "Generates detailed component descriptions." },
  { n: "04", name: "Pseudocode Agent", desc: "Translates descriptions into algorithmic pseudocode." },
  { n: "05", name: "RTL Generation Agent", desc: "Generates synthesisable Verilog RTL code." },
  { n: "06", name: "RTL Verification Agent", desc: "Verifies RTL against the specification." },
  { n: "07", name: "Reflection Agent", desc: "Reflects on errors and guides RTL regeneration." },
];

export default function Settings() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:px-8 md:py-8">
      {/* Header */}
      <header className="mb-6">
        <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-[0.16em] text-[var(--acc2)]">
          <Settings2 size={13} />
          Settings
        </div>
        <h1 className="mt-1 font-mono text-2xl md:text-3xl font-extrabold tracking-tight text-[var(--text)]">Application Info</h1>
        <p className="mt-2 text-xs text-[var(--mute)]">
          SPEC2RTL — multi-agent hardware specification to RTL pipeline.
        </p>
      </header>

      {/* Info cards */}
      <div className="grid gap-5">
        {/* App info */}
        <div className="glass p-6">
          <div className="mb-4 flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-gradient-to-br from-[var(--acc2)] to-[var(--acc)] text-[#05080d] font-mono font-extrabold">
              <Cpu size={18} />
            </span>
            <div>
              <div className="font-mono font-bold text-[var(--text)]">SPEC2RTL</div>
              <div className="font-mono text-xs text-[var(--mute)]">Version 1.0 · Multi-Agent Pipeline</div>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              { label: "Frontend", value: "React 18 + Vite + Tailwind CSS v3" },
              { label: "Backend", value: "FastAPI (Python) · port 8000" },
              { label: "Dev server", value: "Vite · port 5173" },
              { label: "API proxy", value: "/api → 127.0.0.1:8000" },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-4 py-3">
                <div className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--mute)]">{item.label}</div>
                <div className="mt-1 font-mono text-sm font-semibold text-[var(--text)]">{item.value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Pipeline stages */}
        <div className="glass p-6">
          <h2 className="mb-4 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">Pipeline Stages</h2>
          <div className="grid gap-2">
            {AGENTS.map((agent) => (
              <div key={agent.n} className="flex items-start gap-3 rounded-lg border border-[var(--line)] bg-[rgba(16,22,32,0.6)] px-4 py-3">
                <span className="mt-0.5 shrink-0 rounded-md border border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.1)] px-2 py-0.5 font-mono text-xs font-bold text-[var(--acc2)]">
                  {agent.n}
                </span>
                <div>
                  <div className="font-mono text-sm font-semibold text-[var(--text)]">{agent.name}</div>
                  <div className="mt-0.5 font-mono text-xs text-[var(--mute)]">{agent.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Backend link */}
        <div className="glass p-6">
          <h2 className="mb-3 font-mono text-xs font-bold uppercase tracking-wider text-[var(--mute)]">Backend API</h2>
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--acc2)]/50 bg-[rgba(167,139,250,0.15)] px-4 py-2.5 font-mono text-xs font-semibold text-[var(--acc2)] transition hover:bg-[rgba(167,139,250,0.28)] hover:text-white"
          >
            Open API Docs <ExternalLink size={13} />
          </a>
        </div>
      </div>
    </div>
  );
}
