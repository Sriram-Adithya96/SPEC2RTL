import { FileText, Upload } from "lucide-react";
import UploadPanel from "../components/UploadPanel";

export default function Composer() {
  return (
    <div className="mx-auto max-w-4xl gap-6 px-4 py-6 md:px-8 md:py-8">
      {/* Page header */}
      <header className="mb-6">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-[#A879E5]">
          <Upload size={13} />
          Specification Composer
        </div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-indigo">Upload Specification</h1>
        <p className="mt-2 max-w-xl text-sm leading-6 text-muted">
          Upload a hardware specification document (PDF or DOCX) to start the multi-agent RTL generation pipeline.
        </p>
      </header>

      {/* Upload card */}
      <div className="glass-card glass-card-hover p-6 md:p-8">
        <div className="mb-5 flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-[#E9DDFB] text-[#7540C5]">
            <FileText size={18} />
          </span>
          <div>
            <div className="font-bold text-indigo">Hardware Specification</div>
            <div className="text-xs text-muted">PDF or DOCX · Max 20 MB</div>
          </div>
        </div>
        <UploadPanel />
      </div>

      {/* Info row */}
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        {[
          { label: "7 Agents", desc: "Understanding → RTL → Verification → Reflection" },
          { label: "Auto Verification", desc: "RTL is automatically verified after generation" },
          { label: "Reflection Loop", desc: "Agent reflects and regenerates if verification fails" },
        ].map((item) => (
          <div key={item.label} className="glass-card px-4 py-4">
            <div className="text-sm font-bold text-indigo">{item.label}</div>
            <div className="mt-1 text-xs leading-5 text-muted">{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

