import { useState } from "react";
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
          valor={formatMoney(today?.revenue)}
          data={formatMoney(yesterday?.revenue)}
          categoria={formatPercentage(comparison?.revenue_change)}
          tendencia={(comparison?.revenue_change ?? 0) < 0 ? "baixa" : "alta"}
        />
        <ValorCard
          nome="Lucro"
          valor={formatMoney(today?.profit)}
          data={formatMoney(yesterday?.profit)}
          categoria={formatPercentage(comparison?.profit_change)}
          tendencia={(comparison?.profit_change ?? 0) < 0 ? "baixa" : "alta"}
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
          hourlyData={hourly}
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
