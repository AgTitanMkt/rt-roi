import React, { useCallback, useEffect, useState } from "react";
import type { ChartComparisonFilters, Filters, FilterContextType } from "./filterContextTypes";
import { FilterContext } from "./filterContextObject";
import { normalizeSquadFilter } from "../utils/squadMapping";

/**
 * FilterProvider: Provider para o contexto de filtros
 */

const DEFAULT_FILTERS: Filters = {
  period: "24h",
  squad: undefined,
  checkout: undefined,
  product: undefined,
  offer: undefined,
  traffic_source: undefined,
  country: undefined,
  date_start: undefined,
  date_end: undefined,
};

const toIsoDate = (value: Date): string => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const now = new Date();
const yesterday = new Date(now);
yesterday.setDate(now.getDate() - 1);

const DEFAULT_CHART_COMPARISON: ChartComparisonFilters = {
  enabled: true,
  base_date: toIsoDate(now),
  compare_date: toIsoDate(yesterday),
};


export const FilterProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const urlParams = new URLSearchParams(window.location.search);

  const [filters, setFiltersState] = useState<Filters>(() => {
    // Recuperar filtros da URL ao carregar
    return {
      period: (urlParams.get("period") as Filters["period"]) || DEFAULT_FILTERS.period,
      squad: normalizeSquadFilter(urlParams.get("squad") || undefined),
      checkout: urlParams.get("checkout") || undefined,
      product: urlParams.get("product") || undefined,
      offer: urlParams.get("offer") || undefined,
      traffic_source: urlParams.get("traffic_source") || undefined,
      country: urlParams.get("country") || undefined,
      date_start: urlParams.get("date_start") || undefined,
      date_end: urlParams.get("date_end") || undefined,
    };
  });

  const [chartComparison, setChartComparisonState] = useState<ChartComparisonFilters>(() => ({
    enabled: urlParams.get("compare_enabled")
      ? urlParams.get("compare_enabled") === "true"
      : DEFAULT_CHART_COMPARISON.enabled,
    base_date: urlParams.get("compare_base_date") || DEFAULT_CHART_COMPARISON.base_date,
    compare_date: urlParams.get("compare_target_date") || DEFAULT_CHART_COMPARISON.compare_date,
  }));

  // Sincronizar filtros com URL
  useEffect(() => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params.set(key, String(value));
      }
    });

    params.set("compare_enabled", String(chartComparison.enabled));
    params.set("compare_base_date", chartComparison.base_date);
    params.set("compare_target_date", chartComparison.compare_date);

    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState(null, "", newUrl);
  }, [filters, chartComparison]);

  const setFilters = useCallback((newFilters: Filters) => {
    setFiltersState(newFilters);
  }, []);

  const setChartComparison = useCallback((newFilters: ChartComparisonFilters) => {
    setChartComparisonState(newFilters);
  }, []);

  const updateFilter = useCallback(<K extends keyof Filters>(key: K, value: Filters[K]) => {
    const nextValue = key === "squad" ? normalizeSquadFilter(value as string | undefined) : value;
    setFiltersState((prev) => ({
      ...prev,
      [key]: nextValue,
    }));
  }, []);

  const updateChartComparison = useCallback(
    <K extends keyof ChartComparisonFilters>(key: K, value: ChartComparisonFilters[K]) => {
      setChartComparisonState((prev) => ({
        ...prev,
        [key]: value,
      }));
    },
    [],
  );

  const resetFilters = useCallback(() => {
    setFiltersState(DEFAULT_FILTERS);
  }, []);

  const resetChartComparison = useCallback(() => {
    setChartComparisonState(DEFAULT_CHART_COMPARISON);
  }, []);

  const getFilterParams = useCallback(() => {
    const params: Record<string, string | undefined> = {};
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params[key] = String(value);
      }
    });
    return params;
  }, [filters]);

  const value: FilterContextType = {
    filters,
    chartComparison,
    setFilters,
    setChartComparison,
    updateFilter,
    updateChartComparison,
    resetFilters,
    resetChartComparison,
    getFilterParams,
  };

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
};


