export function fmtLocal(tsMs) {
  if (!Number.isFinite(tsMs)) return "—";
  try {
    return new Date(tsMs).toLocaleString();
  } catch {
    return "—";
  }
}

export function fmtRange(startMs, endMs) {
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return "—";
  return `${fmtLocal(startMs)} → ${fmtLocal(endMs)}`;
}

export function isoNow() {
  return new Date().toISOString();
}
