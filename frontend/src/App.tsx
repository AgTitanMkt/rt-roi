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
  const backendSquad = selectedSquad === DEFAULT_SQUAD ? undefined : selectedSquad;

  const { summary, hourly, isHealthy, isLoading, error, lastUpdated } =
    useDashboardData({ squad: backendSquad, period: selectedPeriod });

  const today = summary?.today;
  const yesterday = summary?.yesterday;
  const comparison = summary?.comparison;

  const todayRevenue = resolveRevenue(today);
  const yesterdayRevenue = resolveRevenue(yesterday);

  const resolvedRevenueChange =
    comparison?.revenue_change ?? getChangePercent(todayRevenue, yesterdayRevenue);

  const hourlyWithResolvedRevenue = useMemo(
    () =>
      hourly.map((item) => ({
        ...item,
        revenue: resolveRevenue(item),
      })),
    [hourly],
  );

  const checkoutTotals = useMemo(() => {
    const grouped = hourlyWithResolvedRevenue.reduce(
      (acc, item) => {
        const value = Number(item.checkout_conversion ?? 0);
        if (item.day === "yesterday") {
          acc.yesterdaySum += value;
          acc.yesterdayCount += 1;
        } else if (item.day === "today") {
          acc.todaySum += value;
          acc.todayCount += 1;
        }
        return acc;
      },
      { todaySum: 0, todayCount: 0, yesterdaySum: 0, yesterdayCount: 0 },
    );

    return {
      today: grouped.todayCount > 0 ? grouped.todaySum / grouped.todayCount : 0,
      yesterday: grouped.yesterdayCount > 0 ? grouped.yesterdaySum / grouped.yesterdayCount : 0,
    };
  }, [hourlyWithResolvedRevenue]);

  const checkoutChange = getChangePercent(checkoutTotals.today, checkoutTotals.yesterday);

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
        <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
          <div className="filterGroup">
            <label htmlFor="period-select" style={{ marginRight: "8px", fontWeight: 500 }}>
              Período:
            </label>
            <select
              id="period-select"
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value as "24h" | "daily" | "weekly" | "monthly")}
              style={{
                background: "#111827",
                border: "1px solid #374151",
                color: "#e5e7eb",
                borderRadius: "8px",
                fontSize: "12px",
                padding: "6px 10px",
                width: "min(220px, 100%)",
                minWidth: "150px",
              }}
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
          sufixo="%"
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
          period={selectedPeriod}
        />
      </section>
    </div>
  );
}

export default App;
