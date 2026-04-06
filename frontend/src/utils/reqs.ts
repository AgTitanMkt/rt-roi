import { useCallback, useEffect, useState } from "react";

// Support both relative path (/api) for Docker/local and absolute URL for VPS
const API_BASE =  "/api";

console.log(`[API] Using base URL: ${API_BASE}`);

export const DEFAULT_SQUAD = "all";


export interface MetricsData {
  cost: number;
  profit: number;
  roi: number;
  revenue: number;
  checkout: number;
}

export interface SummaryResponse {
  today: MetricsData;
  yesterday: MetricsData;
  comparison: {
    cost_change: number;
    profit_change: number;
    revenue_change: number;
    checkout_change: number;
    roi_change: number;
  };
}

export interface HourlyMetric {
  squad: string;
  metric_date?: string;
  slot: string;
  day: "today" | "yesterday" | string;
  hour: string;
  checkout_conversion: number;
  cost: number;
  profit: number;
  revenue: number;
  roi: number;
}

export interface CheckoutMetric {
  checkout: string;
  initiate_checkout: number;
  purchase: number;
  checkout_conversion: number;
}

export interface ProductMetric {
  product: string;
  initiate_checkout: number;
  purchase: number;
  checkout_conversion: number;
}

export interface SquadMetric {
  squad: string;
  cost: number;
  profit: number;
  revenue: number;
  checkout_conversion: number;
  roi: number;
}

export interface ConversionBreakdownMetric {
  metric_date?: string;
  squad: string;
  checkout: string;
  product: string;
  initiate_checkout: number;
  purchase: number;
  checkout_conversion: number;
}

export interface OfferResponse {
  offer_id: string;
  name: string;
  status: "found" | "not_found" | "invalid";
  data: Record<string, unknown>;
}

interface HealthResponse {
  status: string;
}

export interface ChartComparisonSeries {
  date: string;
  hourly: HourlyMetric[];
  conversion_breakdown: ConversionBreakdownMetric[];
}

export interface ChartComparisonResponse {
  base_date: string;
  compare_date: string;
  base: ChartComparisonSeries;
  compare: ChartComparisonSeries;
}

interface UseDashboardDataParams {
  squad?: string;
  period?: "24h" | "daily" | "weekly" | "monthly";
  refreshMs?: number;
}

interface UseDashboardDataResult {
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

const withSquad = (path: string, squad?: string): string => {
  if (!squad || squad === DEFAULT_SQUAD) return path;

  // Compatibilidade com backend atual (query param ainda chamado source).
  const params = new URLSearchParams({ source: squad });
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}${params.toString()}`;
};

const fetchJson = async <T>(path: string): Promise<T> => {
  const fullUrl = `${API_BASE}${path}`;
  console.log(`[API] GET ${fullUrl}`);

  try {
    const response = await fetch(fullUrl, {
      cache: "no-store",
      headers: {
        "Cache-Control": "no-cache",
        Pragma: "no-cache",
      },
    });

    if (!response.ok) {
      const errorBody = await response.text();
      console.error(`[API] Error ${response.status} at ${fullUrl}:`, errorBody);
      throw new Error(`Falha na API (${response.status}) em ${path}`);
    }

    const data = await response.json() as T;
    console.log(`[API] Success ${fullUrl}:`, data);
    return data;
  } catch (error) {
    console.error(`[API] Exception at ${fullUrl}:`, error);
    throw error;
  }
};

export const fetchSummary = (
  squad?: string,
  period: string = "24h",
  checkout?: string,
  product?: string,
  forceRefresh: boolean = false,
): Promise<SummaryResponse> => {
  let path = `/metrics/summary?period=${period}`;
  if (squad && squad !== DEFAULT_SQUAD) path += `&source=${squad}`;
  if (checkout && checkout !== DEFAULT_SQUAD) path += `&checkout=${checkout}`;
  if (product && product !== DEFAULT_SQUAD) path += `&product=${product}`;
  if (forceRefresh) path += "&force_refresh=true";
  return fetchJson<SummaryResponse>(path);
};

export const fetchHourly = (
  squad?: string,
  period: string = "24h",
  checkout?: string,
  product?: string,
  dateStart?: string,
  dateEnd?: string,
): Promise<HourlyMetric[]> => {
  let path = `/metrics/hourly/period?period=${period}`;
  if (squad && squad !== DEFAULT_SQUAD) path += `&source=${squad}`;
  if (checkout && checkout !== DEFAULT_SQUAD) path += `&checkout=${checkout}`;
  if (product && product !== DEFAULT_SQUAD) path += `&product=${product}`;
  if (dateStart) path += `&date_start=${dateStart}`;
  if (dateEnd) path += `&date_end=${dateEnd}`;
  return fetchJson<HourlyMetric[]>(path);
};

export const fetchCheckoutMetrics = (squad?: string, period: string = "24h"): Promise<CheckoutMetric[]> => {
  const path = `/metrics/by-checkout?period=${period}`;
  return fetchJson<CheckoutMetric[]>(withSquad(path, squad));
};

export const fetchProductMetrics = (squad?: string, period: string = "24h"): Promise<ProductMetric[]> => {
  const path = `/metrics/by-product?period=${period}`;
  return fetchJson<ProductMetric[]>(withSquad(path, squad));
};

export const fetchSquadMetrics = (period: string = "24h"): Promise<SquadMetric[]> => {
  return fetchJson<SquadMetric[]>(`/metrics/by-squad?period=${period}`);
};

export const fetchConversionBreakdown = (
  period: string = "24h",
  squad?: string,
  checkout?: string,
  product?: string,
  dateStart?: string,
  dateEnd?: string,
): Promise<ConversionBreakdownMetric[]> => {
  let path = `/metrics/conversion-breakdown?period=${period}`;
  // Não enviar "all" como squad - deixar em branco significa todos os squads
  if (squad && squad !== DEFAULT_SQUAD) path += `&squad=${squad}`;
  if (checkout && checkout !== DEFAULT_SQUAD) path += `&checkout=${checkout}`;
  if (product && product !== DEFAULT_SQUAD) path += `&product=${product}`;
  if (dateStart) path += `&date_start=${dateStart}`;
  if (dateEnd) path += `&date_end=${dateEnd}`;
  return fetchJson<ConversionBreakdownMetric[]>(path);
};

export const fetchChartsCompare = (
  baseDate: string,
  compareDate: string,
  squad?: string,
  checkout?: string,
  product?: string,
): Promise<ChartComparisonResponse> => {
  let path = `/metrics/charts/compare?base_date=${encodeURIComponent(baseDate)}&compare_date=${encodeURIComponent(compareDate)}`;
  if (squad && squad !== DEFAULT_SQUAD) path += `&source=${encodeURIComponent(squad)}`;
  if (checkout && checkout !== DEFAULT_SQUAD) path += `&checkout=${encodeURIComponent(checkout)}`;
  if (product && product !== DEFAULT_SQUAD) path += `&product=${encodeURIComponent(product)}`;
  return fetchJson<ChartComparisonResponse>(path);
};

export const checkBackendHealth = async (): Promise<boolean> => {
  const health = await fetchJson<HealthResponse>("/health");
  return health.status === "ok";
};

export const fetchCartpandaOffer = (offerId: string): Promise<OfferResponse> => {
  if (!offerId || !offerId.trim()) {
    return Promise.reject(new Error("offer_id é obrigatório"));
  }
  const path = `/metrics/cartpanda/offer/${encodeURIComponent(offerId)}`;
  return fetchJson<OfferResponse>(path);
};

export const useDebouncedValue = <T>(value: T, delayMs = 250): T => {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timeout);
  }, [value, delayMs]);

  return debounced;
};

export const useDashboardData = ({
  squad,
  period = "24h",
  refreshMs = 60_000,
}: UseDashboardDataParams = {}): UseDashboardDataResult => {
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

  const loadDashboardData = useCallback(async () => {
    setError(null);
    setIsLoading(true);

    try {
      const healthy = await checkBackendHealth().catch(() => false);
      setIsHealthy(healthy);

      const [summaryResult, hourlyResult, checkoutsResult, productsResult, squadsResult, breakdownResult] = await Promise.allSettled([
        fetchSummary(squad, period),
        fetchHourly(squad, period),
        fetchCheckoutMetrics(squad, period),
        fetchProductMetrics(squad, period),
        fetchSquadMetrics(period),
        fetchConversionBreakdown(period),
      ]);

      const errors: string[] = [];

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      } else {
        errors.push("Falha ao atualizar cards (summary)");
      }

      if (hourlyResult.status === "fulfilled") {
        setHourly(hourlyResult.value);
      } else {
        // Mantem cards funcionando quando grafico falha.
        setHourly([]);
        errors.push("Falha ao atualizar grafico (hourly)");
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
    } finally {
      setIsLoading(false);
    }
  }, [squad, period]);

  useEffect(() => {
    void loadDashboardData();

    const intervalId = window.setInterval(() => {
      void loadDashboardData();
    }, refreshMs);

    return () => window.clearInterval(intervalId);
  }, [loadDashboardData, refreshMs, period]);

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
    refreshNow: loadDashboardData,
  };
};
