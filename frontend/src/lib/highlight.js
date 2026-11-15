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
      let color = "color:#7540C5";
      if (match.startsWith('"')) {
        color = match.trimEnd().endsWith(":")
          ? "color:#35145D;font-weight:600"
          : "color:#7540C5";
      } else if (match === "true" || match === "false") {
        color = "color:#0f766e";
      } else if (match === "null") {
        color = "color:#4A3566";
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
    '<span style="color:#7540C5;font-weight:600">$1</span>',
  );
}
