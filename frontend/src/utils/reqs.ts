import { useCallback, useEffect, useState } from "react";

// Support both relative path (/api) for Docker/local and absolute URL for VPS
const API_BASE =  "/api";

console.log(`[API] Using base URL: ${API_BASE}`);

export interface SquadOption {
  value: string;
  label: string;
}

export const DEFAULT_SQUAD = "all";

export const SQUAD_OPTIONS: SquadOption[] = [
  { value: DEFAULT_SQUAD, label: "Todos os squads" },
  { value: "FBR", label: "Facebook" },
  { value: "NTE", label: "Native - Erick" },
  { value: "NTL", label: "Native - Luigi" },
  { value: "YTD", label: "Youtube Fenix" },
  { value: "YTS", label: "Youtube Shenlong" }
];

export interface MetricsData {
  cost: number;
  profit: number;
  roi: number;
  revenue: number;
}

export interface SummaryResponse {
  today: MetricsData;
  yesterday: MetricsData;
  comparison: {
    cost_change: number;
    profit_change: number;
    revenue_change: number;
    roi_change: number;
  };
}

export interface HourlyMetric {
  squad: string;
  hour: string;
  cost: number;
  profit: number;
  revenue: number;
  roi: number;
}

interface HealthResponse {
  status: string;
}

interface UseDashboardDataParams {
  squad?: string;
  refreshMs?: number;
}

interface UseDashboardDataResult {
  summary: SummaryResponse | null;
  hourly: HourlyMetric[];
  isHealthy: boolean;
  isLoading: boolean;
  error: string | null;
  lastUpdated: number | null;
  refreshNow: () => Promise<void>;
}

const withSquad = (path: string, squad?: string): string => {
  if (!squad) return path;

  // Compatibilidade com backend atual (query param ainda chamado source).
  const params = new URLSearchParams({ source: squad });
  return `${path}?${params.toString()}`;
};

const fetchJson = async <T>(path: string): Promise<T> => {
  const fullUrl = `${API_BASE}${path}`;
  console.log(`[API] GET ${fullUrl}`);

  try {
    const response = await fetch(fullUrl);

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

export const fetchSummary = (squad?: string): Promise<SummaryResponse> =>
  fetchJson<SummaryResponse>(withSquad("/metrics/summary", squad));

export const fetchHourly = (squad?: string): Promise<HourlyMetric[]> =>
  fetchJson<HourlyMetric[]>(withSquad("/metrics/hourly", squad));

export const checkBackendHealth = async (): Promise<boolean> => {
  const health = await fetchJson<HealthResponse>("/health");
  return health.status === "ok";
};

export const useDashboardData = ({
  squad,
  refreshMs = 60_000,
}: UseDashboardDataParams = {}): UseDashboardDataResult => {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [hourly, setHourly] = useState<HourlyMetric[]>([]);
  const [isHealthy, setIsHealthy] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);

  const loadDashboardData = useCallback(async () => {
    setError(null);

    try {
      const [healthy, summaryData, hourlyData] = await Promise.all([
        checkBackendHealth(),
        fetchSummary(squad),
        fetchHourly(squad),
      ]);

      setIsHealthy(healthy);
      setSummary(summaryData);
      setHourly(hourlyData);
      setLastUpdated(Date.now());
    } catch (err) {
      setIsHealthy(false);
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [squad]);

  useEffect(() => {
    void loadDashboardData();

    const intervalId = window.setInterval(() => {
      void loadDashboardData();
    }, refreshMs);

    return () => window.clearInterval(intervalId);
  }, [loadDashboardData, refreshMs]);

  return {
    summary,
    hourly,
    isHealthy,
    isLoading,
    error,
    lastUpdated,
    refreshNow: loadDashboardData,
  };
};
