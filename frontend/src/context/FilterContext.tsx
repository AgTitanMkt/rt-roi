import React, { useCallback, useEffect, useState } from "react";
import type { Filters, FilterContextType } from "./filterContextTypes";
import { FilterContext } from "./filterContextObject";

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


export const FilterProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [filters, setFiltersState] = useState<Filters>(() => {
    // Recuperar filtros da URL ao carregar
    const params = new URLSearchParams(window.location.search);
    return {
      period: (params.get("period") as Filters["period"]) || DEFAULT_FILTERS.period,
      squad: params.get("squad") || undefined,
      checkout: params.get("checkout") || undefined,
      product: params.get("product") || undefined,
      offer: params.get("offer") || undefined,
      traffic_source: params.get("traffic_source") || undefined,
      country: params.get("country") || undefined,
      date_start: params.get("date_start") || undefined,
      date_end: params.get("date_end") || undefined,
    };
  });

  // Sincronizar filtros com URL
  useEffect(() => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params.set(key, String(value));
      }
    });
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState(null, "", newUrl);
  }, [filters]);

  const setFilters = useCallback((newFilters: Filters) => {
    setFiltersState(newFilters);
  }, []);

  const updateFilter = useCallback(<K extends keyof Filters>(key: K, value: Filters[K]) => {
    setFiltersState((prev) => ({
      ...prev,
      [key]: value,
    }));
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(DEFAULT_FILTERS);
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
    setFilters,
    updateFilter,
    resetFilters,
    getFilterParams,
  };

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
};


