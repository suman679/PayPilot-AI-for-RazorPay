export default function PolicyBadge({ notice }) {
  if (!notice) return null;
  const blocked = !notice.allowed;
  return (
    <div
      className={`mt-2 rounded-lg border px-3 py-2 text-xs font-mono ${
        blocked
          ? "border-danger/40 bg-danger/10 text-danger"
          : "border-signal/40 bg-signal/10 text-signal"
      }`}
    >
      <div className="uppercase tracking-wide text-[10px] mb-1 opacity-80">
        {blocked ? "policy: blocked" : "policy: allowed"}
      </div>
      <ul className="space-y-0.5">
        {(notice.explanation || []).map((line, i) => (
          <li key={i}>• {line}</li>
        ))}
      </ul>
    </div>
  );
}
