const LEGACY_TO_CANONICAL: Record<string, string> = {
  fbr: "fb",
  fb: "fb",
  nte: "nte",
  ntl: "ntl",
  ntm: "nte",
  ytd: "ytf",
  ytf: "ytf",
  ytl: "yts",
  yts: "yts",
  tkj: "unknown",
  taboola: "unknown",
};

const SQUAD_CANONICAL = new Set(["fb", "nte", "ntl", "ytf", "yts"]);

export const normalizeSquadFilter = (value?: string): string | undefined => {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw || raw === "all") return undefined;

  const mapped = LEGACY_TO_CANONICAL[raw] ?? raw;
  if (mapped === "unknown") return raw;
  if (SQUAD_CANONICAL.has(mapped)) return mapped;

  // Preserva valor original para backend filtrar mesmo sem alias canônico.
  return raw;
};

