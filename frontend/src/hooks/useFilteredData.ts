import { useCallback, useEffect, useState } from "react";
import { useFilters } from "../context/useFilters";
import type { Filters } from "../context/filterContextTypes";
import {
  fetchSummary,
  fetchHourly,
  fetchCheckoutMetrics,
  fetchProductMetrics,
  fetchSquadMetrics,
  fetchConversionBreakdown,
  checkBackendHealth,
} from "../utils/reqs";
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
  const { filters } = useFilters();

  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [hourly, setHourly] = useState<HourlyMetric[]>([]);
  const [checkouts, setCheckouts] = useState<CheckoutMetric[]>([]);
  const [products, setProducts] = useState<ProductMetric[]>([]);
  const [squads, setSquads] = useState<SquadMetric[]>([]);
  const [conversionBreakdown, setConversionBreakdown] = useState<ConversionBreakdownMetric[]>([]);
  const [isHealthy, setIsHealthy] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);

  /**
   * Converte FilterContext.Filters para parâmetros de requisição
   * Mapeia squad para source (compatibilidade com backend)
   */
  const buildApiParams = useCallback((filters: Filters) => {
    return {
      period: filters.period,
      source: filters.squad, // Backend espera "source" em lugar de "squad"
      squad: filters.squad,
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
  const loadAllData = useCallback(async () => {
    setError(null);
    setIsLoading(true);

    try {
      const healthy = await checkBackendHealth().catch(() => false);
      setIsHealthy(healthy);

      const params = buildApiParams(filters);

      // Fazer todas as requisições em paralelo
      const [
        summaryResult,
        hourlyResult,
        checkoutsResult,
        productsResult,
        squadsResult,
        breakdownResult,
      ] = await Promise.allSettled([
        fetchSummary(params.source, params.period, params.checkout, params.product),
        fetchHourly(params.source, params.period, params.checkout, params.product),
        fetchCheckoutMetrics(params.source, params.period),
        fetchProductMetrics(params.source, params.period),
        fetchSquadMetrics(params.period),
        fetchConversionBreakdown(params.period, params.squad, params.checkout, params.product),
      ]);

      const errors: string[] = [];

      // Processar resultados
      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      } else {
        errors.push("Falha ao atualizar cards");
        console.error("Summary error:", summaryResult.reason);
      }

      if (hourlyResult.status === "fulfilled") {
        setHourly(hourlyResult.value);
      } else {
        setHourly([]);
        errors.push("Falha ao atualizar gráfico");
        console.error("Hourly error:", hourlyResult.reason);
      }

      if (checkoutsResult.status === "fulfilled") {
        setCheckouts(checkoutsResult.value);
      } else {
        setCheckouts([]);
      }

      if (productsResult.status === "fulfilled") {
        setProducts(productsResult.value);
      } else {
        setProducts([]);
      }

      if (squadsResult.status === "fulfilled") {
        setSquads(squadsResult.value);
      } else {
        setSquads([]);
      }

      if (breakdownResult.status === "fulfilled") {
        setConversionBreakdown(breakdownResult.value);
      } else {
        setConversionBreakdown([]);
      }

      if (errors.length > 0) {
        setError(errors.join(" | "));
      }

      if (summaryResult.status === "fulfilled" || hourlyResult.status === "fulfilled") {
        setLastUpdated(Date.now());
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
      console.error("useFilteredData error:", err);
    } finally {
      setIsLoading(false);
    }
  }, [filters, buildApiParams]);

  // Recarregar dados quando filtros mudam
  useEffect(() => {
    void loadAllData();
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
    isHealthy,
    isLoading,
    error,
    lastUpdated,
    refreshNow: loadAllData,
  };
};

