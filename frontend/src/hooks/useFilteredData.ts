import { useCallback, useEffect, useRef, useState } from "react";
import { useFilters } from "../context/useFilters";
import type { Filters } from "../context/filterContextTypes";
import {
  fetchSummary,
  fetchHourly,
  fetchCheckoutMetrics,
  fetchProductMetrics,
  fetchSquadMetrics,
  fetchConversionBreakdown,
  fetchChartsCompare,
  checkBackendHealth,
} from "../utils/reqs";
import { normalizeSquadFilter } from "../utils/squadMapping";
import { isAdmin } from "../services/authService";
import type {
  SummaryResponse,
  HourlyMetric,
  CheckoutMetric,
  ProductMetric,
  SquadMetric,
  ConversionBreakdownMetric,
} from "../utils/reqs";

/**
 * useFilteredData: Hook que sincroniza filtros com requisições da API
 * Sempre que os filtros mudam, faz requisições a todas as rotas
 */

export interface UseFilteredDataResult {
  summary: SummaryResponse | null;
  hourly: HourlyMetric[];
  checkouts: CheckoutMetric[];
  products: ProductMetric[];
  squads: SquadMetric[];
  conversionBreakdown: ConversionBreakdownMetric[];
  chartComparisonData: {
    baseDate: string;
    compareDate: string;
    hourlyBase: HourlyMetric[];
    hourlyCompare: HourlyMetric[];
    breakdownBase: ConversionBreakdownMetric[];
    breakdownCompare: ConversionBreakdownMetric[];
  } | null;
  isHealthy: boolean;
  isLoading: boolean;
  error: string | null;
  lastUpdated: number | null;
  refreshNow: () => Promise<void>;
}

interface UseFilteredDataParams {
  refreshMs?: number; // Intervalo de atualização automática em ms
}

export const useFilteredData = ({
  refreshMs = 60_000,
}: UseFilteredDataParams = {}): UseFilteredDataResult => {
  const { filters, chartComparison } = useFilters();

  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [hourly, setHourly] = useState<HourlyMetric[]>([]);
  const [checkouts, setCheckouts] = useState<CheckoutMetric[]>([]);
  const [products, setProducts] = useState<ProductMetric[]>([]);
  const [squads, setSquads] = useState<SquadMetric[]>([]);
  const [conversionBreakdown, setConversionBreakdown] = useState<ConversionBreakdownMetric[]>([]);
  const [chartComparisonData, setChartComparisonData] = useState<UseFilteredDataResult["chartComparisonData"]>(
    null,
  );
  const [isHealthy, setIsHealthy] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const requestIdRef = useRef(0);

  /**
   * Converte FilterContext.Filters para parâmetros de requisição
   * Mapeia squad para source (compatibilidade com backend)
   */
  const buildApiParams = useCallback((filters: Filters) => {
    const normalizedSquad = normalizeSquadFilter(filters.squad);
    return {
      period: filters.period,
      source: normalizedSquad, // Backend espera "source" em lugar de "squad"
      squad: normalizedSquad,
      checkout: filters.checkout,
      product: filters.product,
      offer: filters.offer,
      traffic_source: filters.traffic_source,
      country: filters.country,
      date_start: filters.date_start,
      date_end: filters.date_end,
    };
  }, []);

  /**
   * Faz todas as requisições em paralelo
   */
  const loadAllData = useCallback(async (resetSummary = false) => {
    const requestId = ++requestIdRef.current;

    setError(null);
    setIsLoading(true);
    if (resetSummary) {
      // Evita mostrar cards antigos enquanto os filtros novos carregam.
      setSummary(null);
    }

    try {
      const params = buildApiParams(filters);

      const errors: string[] = [];

      const healthPromise = checkBackendHealth()
        .then((healthy) => {
          if (requestId === requestIdRef.current) setIsHealthy(healthy);
        })
        .catch(() => {
          if (requestId === requestIdRef.current) setIsHealthy(false);
        });

      const summaryPromise = fetchSummary(
        params.source,
        params.period,
        params.checkout,
        params.product,
        true,
      )
        .then((value) => {
          if (requestId === requestIdRef.current) setSummary(value);
        })
        .catch((reason) => {
          errors.push("Falha ao atualizar cards");
          console.error("Summary error:", reason);
        });

      const hourlyPromise = fetchHourly(params.source, params.period, params.checkout, params.product)
        .then((value) => {
          if (requestId === requestIdRef.current) setHourly(value);
        })
        .catch((reason) => {
          if (requestId === requestIdRef.current) setHourly([]);
          errors.push("Falha ao atualizar gráfico");
          console.error("Hourly error:", reason);
        });

      const checkoutsPromise = fetchCheckoutMetrics(params.source, params.period)
        .then((value) => {
          if (requestId === requestIdRef.current) setCheckouts(value);
        })
        .catch(() => {
          if (requestId === requestIdRef.current) setCheckouts([]);
        });

      const productsPromise = fetchProductMetrics(params.source, params.period)
        .then((value) => {
          if (requestId === requestIdRef.current) setProducts(value);
        })
        .catch(() => {
          if (requestId === requestIdRef.current) setProducts([]);
        });

      const squadsPromise = isAdmin()
        ? fetchSquadMetrics(params.period)
            .then((value) => {
              if (requestId === requestIdRef.current) setSquads(value);
            })
            .catch(() => {
              if (requestId === requestIdRef.current) setSquads([]);
            })
        : Promise.resolve().then(() => {
            if (requestId === requestIdRef.current) setSquads([]);
          });

      const breakdownPromise = fetchConversionBreakdown(params.period, params.squad, params.checkout, params.product)
        .then((value) => {
          if (requestId === requestIdRef.current) setConversionBreakdown(value);
        })
        .catch(() => {
          if (requestId === requestIdRef.current) setConversionBreakdown([]);
        });

       const chartComparisonPromise = chartComparison.enabled
         ? fetchChartsCompare(
             chartComparison.base_date,
             chartComparison.compare_date,
             params.period,
             params.source,
             params.checkout,
             params.product,
           )
            .then((payload) => {
              if (requestId === requestIdRef.current) {
                setChartComparisonData({
                  baseDate: payload.base_date,
                  compareDate: payload.compare_date,
                  hourlyBase: payload.base.hourly,
                  hourlyCompare: payload.compare.hourly,
                  breakdownBase: payload.base.conversion_breakdown,
                  breakdownCompare: payload.compare.conversion_breakdown,
                });
              }
            })
            .catch(() => {
              if (requestId === requestIdRef.current) setChartComparisonData(null);
            })
        : Promise.resolve().then(() => {
            if (requestId === requestIdRef.current) setChartComparisonData(null);
          });

      await Promise.all([
        healthPromise,
        summaryPromise,
        hourlyPromise,
        checkoutsPromise,
        productsPromise,
        squadsPromise,
        breakdownPromise,
        chartComparisonPromise,
      ]);

      if (errors.length > 0) {
        if (requestId === requestIdRef.current) setError(errors.join(" | "));
      }

      if (requestId === requestIdRef.current) setLastUpdated(Date.now());
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      if (requestId === requestIdRef.current) setError(message);
      console.error("useFilteredData error:", err);
    } finally {
      if (requestId === requestIdRef.current) setIsLoading(false);
    }
  }, [filters, buildApiParams, chartComparison]);

  // Recarregar dados quando filtros mudam
  useEffect(() => {
    void loadAllData(true);
  }, [filters, loadAllData]);

  // Auto-refresh periodicamente
  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void loadAllData();
    }, refreshMs);

    return () => window.clearInterval(intervalId);
  }, [loadAllData, refreshMs]);

  return {
    summary,
    hourly,
    checkouts,
    products,
    squads,
    conversionBreakdown,
    chartComparisonData,
    isHealthy,
    isLoading,
    error,
    lastUpdated,
    refreshNow: loadAllData,
  };
};

