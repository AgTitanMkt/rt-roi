import { useCallback, useEffect, useState } from "react";

const API_BASE = "/api";

export interface SourceOption {
  value: string;
  label: string;
}

export const DEFAULT_SOURCE = "all";

export const SOURCE_OPTIONS: SourceOption[] = [
  { value: DEFAULT_SOURCE, label: "Todas as fontes" },
  { value: "google", label: "Google" },
  { value: "facebook", label: "Facebook" },
  { value: "mgid", label: "MGID" },
  { value: "mediago", label: "MediaGo" },
  { value: "newsbreak", label: "NewsBreak" },
  { value: "taboola", label: "Taboola" },
];

export interface MetricsData {
  cost: number;
  profit: number;
  roi: number;
}

export interface SummaryResponse {
  today: MetricsData;
  yesterday: MetricsData;
  comparison: {
    cost_change: number;
    profit_change: number;
    roi_change: number;
  };
}

export interface HourlyMetric {
  hour: string;
  cost: number;
  profit: number;
  roi: number;
}

interface HealthResponse {
  status: string;
}

interface UseDashboardDataParams {
  source?: string;
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

const withSource = (path: string, source?: string): string => {
  if (!source) return path;

  const params = new URLSearchParams({ source });
  return `${path}?${params.toString()}`;
};

const fetchJson = async <T>(path: string): Promise<T> => {
  const response = await fetch(`${API_BASE}${path}`);

  if (!response.ok) {
    throw new Error(`Falha na API (${response.status}) em ${path}`);
  }

  return (await response.json()) as T;
};

export const fetchSummary = (source?: string): Promise<SummaryResponse> =>
  fetchJson<SummaryResponse>(withSource("/metrics/summary", source));

export const fetchHourly = (source?: string): Promise<HourlyMetric[]> =>
  fetchJson<HourlyMetric[]>(withSource("/metrics/hourly", source));

export const checkBackendHealth = async (): Promise<boolean> => {
  const health = await fetchJson<HealthResponse>("/health");
  return health.status === "ok";
};

export const useDashboardData = ({
  source,
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
        fetchSummary(source),
        fetchHourly(source),
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
  }, [source]);

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
