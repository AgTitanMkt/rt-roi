import { useMemo } from "react";
import "./App.css";
import ValorCard from "./componentes/ValorCard.tsx";
import DashboardGrafico1 from "./componentes/DashboardGrafico1.tsx";
import ConversionInsightsChart from "./componentes/ConversionInsightsChart.tsx";
import FilterBar from "./componentes/FilterBar.tsx";
import { useFilters } from "./context/useFilters.ts";
import { useFilteredData } from "./hooks/useFilteredData.ts";

const resolveRevenue = (metrics?: {
  revenue?: number | null;
  cost?: number | null;
  profit?: number | null;
  roi?: number | null;
}): number => {
  if (!metrics) return 0;
  if (metrics.revenue != null) return metrics.revenue;
  if (metrics.cost != null && metrics.profit != null) return metrics.cost + metrics.profit;
  if (metrics.cost != null && metrics.roi != null) return metrics.cost * (1 + metrics.roi / 100);
  return 0;
};

const getChangePercent = (current: number, previous: number): number => {
  if (previous === 0) {
    return current === 0 ? 0 : 100;
  }

  return ((current - previous) / Math.abs(previous)) * 100;
};

function App() {
  const { filters } = useFilters();
  const { summary, hourly, conversionBreakdown, isHealthy, isLoading, error, lastUpdated } =
    useFilteredData();


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
          <p className="dashboardSubtitle">Visão consolidada para decisão rápida de performance</p>
        </div>
        <div className="dashboardHeaderActions">
          <div className={`statusPill ${isHealthy ? "isOnline" : "isOffline"}`}>
            {isLoading
              ? "Atualizando dados..."
              : isHealthy
                ? `Backend online${lastUpdated ? ` - ${new Date(lastUpdated).toLocaleTimeString()}` : ""}`
                : "Backend indisponível"}
          </div>
        </div>
      </header>

      {/* Filtros Centralizados */}
      <FilterBar compact={false} showAdvanced={false} />

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
          selectedSquad={filters.squad || ""}
          period={filters.period}
        />
      </section>

      <section className="conversionSection">
        <ConversionInsightsChart data={conversionBreakdown} isLoading={isLoading} />
      </section>

    </div>
  );
}

export default App;
