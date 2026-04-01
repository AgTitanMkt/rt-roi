/**
 * filterContextTypes.ts: Tipos e interfaces para FilterContext
 * Separado para evitar conflito com react-refresh
 */

export interface Filters {
  period: "24h" | "daily" | "weekly" | "monthly";
  squad?: string;
  checkout?: string;
  product?: string;
  offer?: string;
  traffic_source?: string;
  country?: string;
  date_start?: string;
  date_end?: string;
}

export interface FilterContextType {
  filters: Filters;
  setFilters: (filters: Filters) => void;
  updateFilter: <K extends keyof Filters>(key: K, value: Filters[K]) => void;
  resetFilters: () => void;
  getFilterParams: () => Record<string, string | undefined>;
}

