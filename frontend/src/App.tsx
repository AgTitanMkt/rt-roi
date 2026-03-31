import { useMemo, useState } from "react";
import "./App.css";
import ValorCard from "./componentes/ValorCard.tsx";
import CardRoi from "./componentes/CardRoi.tsx";
import DashboardGrafico1 from "./componentes/DashboardGrafico1.tsx";
import {
  DEFAULT_SQUAD,
  SQUAD_OPTIONS,
  useDashboardData,
} from "./utils/reqs.ts";


function App() {
  const [selectedSquad, setSelectedSquad] = useState<string>(DEFAULT_SQUAD);
  const backendSquad = selectedSquad === DEFAULT_SQUAD ? undefined : selectedSquad;

  const { summary, hourly, isHealthy, isLoading, error, lastUpdated } =
    useDashboardData({ squad: backendSquad });

  const today = summary?.today;
  const yesterday = summary?.yesterday;
  const comparison = summary?.comparison;

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

  const todayRevenue = resolveRevenue(today);
  const yesterdayRevenue = resolveRevenue(yesterday);

  const resolvedRevenueChange =
    comparison?.revenue_change ??
    (yesterdayRevenue !== 0 ? ((todayRevenue - yesterdayRevenue) / Math.abs(yesterdayRevenue)) * 100 : 0);

  const hourlyWithResolvedRevenue = useMemo(
    () =>
      hourly.map((item) => ({
        ...item,
        revenue: resolveRevenue(item),
      })),
    [hourly],
  );

  const checkoutTotals = useMemo(() => {
    return hourly.reduce(
      (acc, item) => {
        const value = Number(item.checkout_conversion ?? 0);
        if (item.day === "yesterday") {
          acc.yesterday += value;
        } else {
          acc.today += value;
        }
        return acc;
      },
      { today: 0, yesterday: 0 },
    );
  }, [hourly]);

  const checkoutChange =
    checkoutTotals.yesterday !== 0
      ? ((checkoutTotals.today - checkoutTotals.yesterday) / Math.abs(checkoutTotals.yesterday)) * 100
      : 0;

  const formatMoney = (value: number | undefined): number =>
    Number((value ?? 0).toFixed(2));

  const formatPercentage = (value: number | undefined): number =>
    Number(Math.abs(value ?? 0).toFixed(2));

  return (
    <div className="dashboardShell">
      <header className="dashboardHeader">
        <div>
          <h1 className="dashboardTitle">Dashboard de Performance</h1>
          <p className="dashboardSubtitle">Visao consolidada de custo, lucro e ROI</p>
        </div>
        <div className={`statusPill ${isHealthy ? "isOnline" : "isOffline"}`}>
          {isLoading
            ? "Atualizando dados..."
            : isHealthy
              ? `Backend online${lastUpdated ? ` - ${new Date(lastUpdated).toLocaleTimeString()}` : ""}`
              : "Backend indisponivel"}
        </div>
      </header>

      {error && <div className="errorBanner">Erro: {error}</div>}

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
          valor={formatMoney(checkoutTotals.today)}
          data={formatMoney(checkoutTotals.yesterday)}
          categoria={formatPercentage(checkoutChange)}
          tendencia={checkoutChange < 0 ? "baixa" : "alta"}
          prefixo=""
          className="isHighlight"
        />
        <CardRoi
          nome="ROI"
          valor={formatMoney(today?.roi)}
          data={formatMoney(yesterday?.roi)}
          categoria={formatPercentage(comparison?.roi_change)}
          tendencia={(comparison?.roi_change ?? 0) < 0 ? "baixa" : "alta"}
        />

      </section>

      <section className="chartPanel">
        <DashboardGrafico1
          hourlyData={hourlyWithResolvedRevenue}
          isLoading={isLoading}
          selectedSquad={selectedSquad}
          squadOptions={SQUAD_OPTIONS}
          onSquadChange={setSelectedSquad}
        />
      </section>
    </div>
  );
}

export default App;
