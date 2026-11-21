export function formatBytes(size) {
  const value = Number(size);
  if (!Number.isFinite(value) || value < 0) return "Unknown size";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatTokens(count) {
  const value = Number(count);
  if (!Number.isFinite(value) || value <= 0) return "0";
  return value.toLocaleString();
}

export function formatTokensCompact(count) {
  const value = Number(count);
  if (!Number.isFinite(value) || value <= 0) return "0";
  if (value < 1000) return String(value);
  if (value < 1000000) return `${(value / 1000).toFixed(1)}k`;
  return `${(value / 1000000).toFixed(2)}M`;
}

export function getAgentUsage(run, agentId) {
  if (!run?.token_usage?.by_agent) return null;
  const byAgent = run.token_usage.by_agent;
  return (
    byAgent[agentId] ||
    (agentId === "decomposer" ? byAgent["decomposition"] : null) ||
    (agentId === "rtl_verification" ? byAgent["verification"] : null) ||
    null
  );
}

export function asList(value) {
  if (Array.isArray(value)) {
    return value.filter((item) => item !== null && item !== undefined);
  }
  if (value === null || value === undefined || value === "") return [];
  return [value];
}

export function asText(value, fallback = "Not provided") {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export const AGENTS = [
  {
    id: "understanding",
    number: "01",
    name: "Understanding Agent",
    description: "Extracts purpose, interfaces, requirements, constraints, and ambiguities.",
    file: "understanding.json",
  },
  {
    id: "decomposer",
    number: "02",
    name: "Decomposer Agent",
    description: "Organizes the design into components, interactions, and an implementation plan.",
    file: "decomposition.json",
  },
  {
    id: "description",
    number: "03",
    name: "Description Agent",
    description: "Describes each component, including signals, state, and behavior.",
    file: "descriptions.json",
  },
  {
    id: "pseudocode",
    number: "04",
    name: "Pseudocode Generation Agent",
    description: "Generates and validates structured pseudocode for each component.",
    file: "pseudocode.json",
  },
  {
    id: "rtl_generation",
    number: "05",
    name: "RTL Generation Agent",
    description: "Generates component RTL and integrates the top-level module.",
    file: "rtl_generation.json",
  },
  {
    id: "rtl_verification",
    number: "06",
    name: "RTL Verification Agent",
    description: "Checks the generated RTL against the original hardware specification for correctness.",
    file: "rtl_verification.json",
  },
  {
    id: "reflection",
    number: "07",
    name: "Reflection Agent",
    description: "Analyses verification failures and generates targeted RTL correction feedback.",
    file: "reflection.json",
  },
];

export function stageProgress(run) {
  if (!run) return 0;
  if (run.status === "completed") return 100;
  const total = AGENTS.reduce((sum, agent) => {
    const state = run.agents?.[agent.id];
    const status = state?.status || "pending";
    // completed, passed, failed, blocked, skipped, and cancelled all count as a finished stage.
    // A skipped Reflection Agent or passed Verification Agent must not make a successful run appear incomplete.
    if (["completed", "passed", "failed", "blocked", "skipped", "cancelled"].includes(status)) {
      return sum + 1;
    }
    if (status === "running") {
      const components = state.components || [];
      if (!components.length) return sum + 0.15;
      const done = components.filter((item) =>
        ["completed", "failed", "skipped"].includes(item.status),
      ).length;
      return sum + done / components.length;
    }
    return sum;
  }, 0);
  return Math.max(0, Math.min(100, Math.round((total / AGENTS.length) * 100)));
}
