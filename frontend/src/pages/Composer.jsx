import { FileText, Upload } from "lucide-react";
import UploadPanel from "../components/UploadPanel";

export default function Composer() {
  return (
    <div className="mx-auto max-w-4xl gap-6 px-4 py-6 md:px-8 md:py-8">
      {/* Page header */}
      <header className="mb-6">
        <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-[0.16em] text-[var(--acc2)]">
          <Upload size={13} />
          Specification Composer
        </div>
        <h1 className="mt-1 font-mono text-2xl md:text-3xl font-extrabold tracking-tight text-[var(--text)]">Upload Specification</h1>
        <p className="mt-2 max-w-xl text-xs text-[var(--mute)]">
          Upload a hardware specification document (PDF or DOCX) to start the multi-agent RTL generation pipeline.
        </p>
      </header>

      {/* Upload card */}
      <div className="glass p-6 md:p-8 mb-5">
        <div className="mb-5 flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-lg bg-[rgba(125,211,252,0.1)] text-[var(--acc)]">
            <FileText size={18} />
          </span>
          <div>
            <div className="font-mono font-bold text-[var(--text)]">Hardware Specification</div>
            <div className="font-mono text-xs text-[var(--mute)]">PDF or DOCX · Max 20 MB</div>
          </div>
        </div>
        <UploadPanel />
      </div>

      {/* Info row */}
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "7 Agents", desc: "Understanding → RTL → Verification → Reflection" },
          { label: "Auto Verification", desc: "RTL is automatically verified after generation" },
          { label: "Reflection Loop", desc: "Agent reflects and regenerates if verification fails" },
        ].map((item) => (
          <div key={item.label} className="glass px-4 py-4">
            <div className="font-mono text-sm font-bold text-[var(--acc)]">{item.label}</div>
            <div className="mt-1 font-mono text-xs leading-5 text-[var(--mute)]">{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
