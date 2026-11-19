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
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-[#A879E5]">
          <Settings2 size={13} />
          Settings
        </div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-indigo">Application Info</h1>
        <p className="mt-2 text-sm leading-6 text-muted">
          SPEC2RTL — multi-agent hardware specification to RTL pipeline.
        </p>
      </header>

      {/* Info cards */}
      <div className="grid gap-5">
        {/* App info */}
        <div className="glass p-6">
          <div className="mb-4 flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-2xl bg-[#7540C5] text-white shadow-glow">
              <Cpu size={18} />
            </span>
            <div>
              <div className="font-bold text-indigo">SPEC2RTL</div>
              <div className="text-xs text-muted">Version 1.0 · Multi-Agent Pipeline</div>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              { label: "Frontend", value: "React 18 + Vite + Tailwind CSS v3" },
              { label: "Backend", value: "FastAPI (Python) · port 8000" },
              { label: "Dev server", value: "Vite · port 5173" },
              { label: "API proxy", value: "/api → 127.0.0.1:8000" },
            ].map((item) => (
              <div key={item.label} className="rounded-2xl bg-[#F8F5FF] px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-muted">{item.label}</div>
                <div className="mt-1 text-sm font-semibold text-indigo">{item.value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Pipeline stages */}
        <div className="glass p-6">
          <h2 className="mb-4 text-sm font-bold text-indigo">Pipeline Stages</h2>
          <div className="grid gap-2">
            {AGENTS.map((agent) => (
              <div key={agent.n} className="flex items-start gap-3 rounded-xl bg-[#F8F5FF] px-4 py-3">
                <span className="mt-0.5 shrink-0 rounded-lg bg-[#E9DDFB] px-2 py-0.5 text-xs font-bold text-[#7540C5]">
                  {agent.n}
                </span>
                <div>
                  <div className="text-sm font-semibold text-indigo">{agent.name}</div>
                  <div className="text-xs text-muted">{agent.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Backend link */}
        <div className="glass p-6">
          <h2 className="mb-3 text-sm font-bold text-indigo">Backend API</h2>
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-xl bg-[#7540C5] px-4 py-2.5 text-sm font-semibold text-white shadow-glow transition hover:bg-[#35145D]"
          >
            Open API Docs <ExternalLink size={14} />
          </a>
        </div>
      </div>
    </div>
  );
}

