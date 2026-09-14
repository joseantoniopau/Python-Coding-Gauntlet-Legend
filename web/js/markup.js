/* Small prose formatter. Code is a literal token, never parsed as emphasis. */
export function formatProse(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(?:[a-z]+)?\n([\s\S]*?)```|`([^`\n]+)`|\*\*([^*]+)\*\*/g,
      (_, block, inline, bold) => block !== undefined ? `<pre>${block}</pre>`
        : inline !== undefined ? `<code>${inline}</code>`
          : `<b style="color:var(--gold-hi)">${bold}</b>`);
}
