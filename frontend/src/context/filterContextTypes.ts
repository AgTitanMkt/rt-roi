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

export interface ChartComparisonFilters {
  enabled: boolean;
  base_date: string;
  compare_date: string;
}

export interface FilterContextType {
  filters: Filters;
  chartComparison: ChartComparisonFilters;
  setFilters: (filters: Filters) => void;
  setChartComparison: (filters: ChartComparisonFilters) => void;
  updateFilter: <K extends keyof Filters>(key: K, value: Filters[K]) => void;
  updateChartComparison: <K extends keyof ChartComparisonFilters>(
    key: K,
    value: ChartComparisonFilters[K],
  ) => void;
  resetFilters: () => void;
  resetChartComparison: () => void;
  getFilterParams: () => Record<string, string | undefined>;
}

