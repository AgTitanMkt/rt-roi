import { useMemo, useState } from "react";
import "./App.css";
import ValorCard from "./componentes/ValorCard.tsx";
import DashboardGrafico1 from "./componentes/DashboardGrafico1.tsx";
import ConversionInsightsChart from "./componentes/ConversionInsightsChart.tsx";
import {
  DEFAULT_SQUAD,
  SQUAD_OPTIONS,
  useDebouncedValue,
  useDashboardData,
} from "./utils/reqs.ts";

const resolveRevenue = (metrics?: {
  revenue?: number | null;
  cost?: number | null;
  profit?: number | null;
  roi?: number | null;
}): number => {
  if (!metrics) return 0;
  if (metrics.revenue != null) return metrics.revenue;
  if (metrics.cost != null && metrics.profit != null) return metrics.cost + metrics.profit;
  if (metrics.cost != null && metrics.roi != null) return metrics.cost * (1 + metrics.roi);
  return 0;
};

const getChangePercent = (current: number, previous: number): number => {
  if (previous === 0) {
    return current === 0 ? 0 : 100;
  }

  return ((current - previous) / Math.abs(previous)) * 100;
};

function App() {
  const [selectedSquad, setSelectedSquad] = useState<string>(DEFAULT_SQUAD);
  const [selectedPeriod, setSelectedPeriod] = useState<"24h" | "daily" | "weekly" | "monthly">("24h");
  const debouncedSquad = useDebouncedValue(selectedSquad, 250);
  const debouncedPeriod = useDebouncedValue(selectedPeriod, 250);
  const backendSquad = debouncedSquad === DEFAULT_SQUAD ? undefined : debouncedSquad;

  const { summary, hourly, conversionBreakdown, isHealthy, isLoading, error, lastUpdated } =
    useDashboardData({ squad: backendSquad, period: debouncedPeriod });

  const today = summary?.today;
  const yesterday = summary?.yesterday;
  const comparison = summary?.comparison;

  const todayRevenue = resolveRevenue(today);
  const yesterdayRevenue = resolveRevenue(yesterday);

  const resolvedRevenueChange =
    comparison?.revenue_change ?? getChangePercent(todayRevenue, yesterdayRevenue);

  const checkoutToday = Number(today?.checkout ?? 0);
  const checkoutYesterday = Number(yesterday?.checkout ?? 0);
  const checkoutChange =
    comparison?.checkout_change ?? getChangePercent(checkoutToday, checkoutYesterday);

  const hourlyWithResolvedRevenue = useMemo(
    () =>
      hourly.map((item) => ({
        ...item,
        revenue: resolveRevenue(item),
      })),
    [hourly],
  );

  const formatMoney = (value: number | undefined): number =>
    Number((value ?? 0).toFixed(2));

  const formatPercentage = (value: number | undefined): number =>
    Number(Math.abs(value ?? 0).toFixed(2));

  return (
    <div className="dashboardShell">
      <header className="dashboardHeader">
        <div>
          <h1 className="dashboardTitle">Dashboard de Performance</h1>
          <p className="dashboardSubtitle">Visao consolidada para decisao rapida de performance</p>
        </div>
        <div className="dashboardHeaderActions">
          <div className="filterGroup">
            <label htmlFor="period-select" className="ui-label">
              Período:
            </label>
            <select
              id="period-select"
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value as "24h" | "daily" | "weekly" | "monthly")}
              className="ui-select"
            >
              <option value="24h">Últimas 24h</option>
              <option value="daily">Diário</option>
              <option value="weekly">Semanal</option>
              <option value="monthly">Mensal</option>
            </select>
          </div>
          <div className={`statusPill ${isHealthy ? "isOnline" : "isOffline"}`}>
            {isLoading
              ? "Atualizando dados..."
              : isHealthy
                ? `Backend online${lastUpdated ? ` - ${new Date(lastUpdated).toLocaleTimeString()}` : ""}`
                : "Backend indisponivel"}
          </div>
        </div>
      </header>

      {error && <div className="errorBanner">Erro: {error}</div>}

      {isLoading && !summary ? (
        <section className="cardsGrid" aria-busy="true">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={`skeleton-${index}`} className="kpiSkeleton ui-card" />
          ))}
        </section>
      ) : (
        <section className="cardsGrid">
          <ValorCard
            nome="Gasto"
            valor={formatMoney(today?.cost)}
            data={formatMoney(yesterday?.cost)}
            categoria={formatPercentage(comparison?.cost_change)}
            tendencia={(comparison?.cost_change ?? 0) < 0 ? "baixa" : "alta"}
          />
          <ValorCard
            nome="Faturamento"
            valor={formatMoney(todayRevenue)}
            data={formatMoney(yesterdayRevenue)}
            categoria={formatPercentage(resolvedRevenueChange)}
            tendencia={resolvedRevenueChange < 0 ? "baixa" : "alta"}
          />
          <ValorCard
            nome="Lucro"
            valor={formatMoney(today?.profit)}
            data={formatMoney(yesterday?.profit)}
            categoria={formatPercentage(comparison?.profit_change)}
            tendencia={(comparison?.profit_change ?? 0) < 0 ? "baixa" : "alta"}
          />
          <ValorCard
            nome="Checkout"
            valor={formatMoney(checkoutToday)}
            data={formatMoney(checkoutYesterday)}
            categoria={formatPercentage(checkoutChange)}
            tendencia={checkoutChange < 0 ? "baixa" : "alta"}
            prefixo=""
            sufixo="%"
            className="isHighlight"
          />
          <ValorCard
            nome="ROI"
            valor={formatMoney(today?.roi)}
            data={formatMoney(yesterday?.roi)}
            categoria={formatPercentage(comparison?.roi_change)}
            tendencia={(comparison?.roi_change ?? 0) < 0 ? "baixa" : "alta"}
            prefixo=""
            sufixo="%"
            className="isHighlight"
          />
        </section>
      )}

      <section className="chartPanel">
        <DashboardGrafico1
          hourlyData={hourlyWithResolvedRevenue}
          isLoading={isLoading}
          selectedSquad={selectedSquad}
          squadOptions={SQUAD_OPTIONS}
          onSquadChange={setSelectedSquad}
          period={selectedPeriod}
        />
      </section>

      <section className="conversionSection">
        <ConversionInsightsChart data={conversionBreakdown} isLoading={isLoading} />
      </section>

    </div>
  );
}

export default App;
