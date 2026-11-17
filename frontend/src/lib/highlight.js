function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

export function highlightJson(text) {
  const source = escapeHtml(text);
  return source.replace(
    /("(?:\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(\s*:)?|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      let color = "color:var(--acc2,#a78bfa)";
      if (match.startsWith('"')) {
        color = match.trimEnd().endsWith(":")
          ? "color:var(--acc,#7dd3fc);font-weight:600"
          : "color:var(--acc2,#a78bfa)";
      } else if (match === "true" || match === "false") {
        color = "color:var(--ok,#4ade80)";
      } else if (match === "null") {
        color = "color:var(--mute,#7d8aa3)";
      } else {
        color = "color:var(--warn,#fbbf24)";
      }
      return `<span style="${color}">${match}</span>`;
    },
  );
}

const PSEUDO_KEYWORDS =
  /\b(MODULE|END MODULE|INPUT|OUTPUT|INOUT|CLOCK|EDGE|RISING|FALLING|REG|SIG|PARAMETER|CONST|STATE|BLOCK|COMBINATIONAL|CLOCKED|END BLOCK|IF|ELSE|END IF|CASE|WHEN|END CASE|ASSIGN|RESET|END RESET|FUNCTION|END FUNCTION|UNRESOLVED)\b/g;

export function highlightPseudocode(line) {
  return escapeHtml(line).replace(
    PSEUDO_KEYWORDS,
    '<span style="color:var(--acc2,#a78bfa);font-weight:600">$1</span>',
  );
}
