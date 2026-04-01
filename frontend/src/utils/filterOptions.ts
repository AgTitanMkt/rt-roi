/**
 * filterOptions.ts: Opções para dropdowns do FilterBar
 * Separado de FilterBar.tsx para evitar conflito com react-refresh
 */

export const PERIOD_OPTIONS = [
  { value: "24h", label: "Últimas 24h" },
  { value: "daily", label: "Diário" },
  { value: "weekly", label: "Semanal" },
  { value: "monthly", label: "Mensal" },
];

export const SQUAD_OPTIONS = [
  { value: "", label: "Todos os squads" },
  { value: "yts", label: "YT Shenlong" },
  { value: "ytf", label: "YT Fenix" },
  { value: "nte", label: "Native Erick" },
  { value: "ntl", label: "Native Luigi" },
  { value: "fb", label: "Facebook" },
];

export const CHECKOUT_OPTIONS = [
  { value: "", label: "Todos os checkouts" },
  { value: "Cartpanda", label: "Cartpanda" },
  { value: "Clickbank", label: "Clickbank" },
];

