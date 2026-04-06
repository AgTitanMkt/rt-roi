import { useMemo } from "react";
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import type { HourlyMetric } from "../utils/reqs.ts";

const HOURS_PER_DAY = 24;

type CompareLabel = {
  baseDate: string;
  compareDate: string;
};

interface DashboardGraficoProps {
  hourlyData: HourlyMetric[];
  comparedHourlyData?: HourlyMetric[];
  isLoading?: boolean;
  selectedSquad: string;
  period?: "24h" | "daily" | "weekly" | "monthly";
  compareLabel?: CompareLabel;
}

type HourAgg = {
  checkout: number;
  gasto: number;
  faturamento: number;
  relacao: number;
  count: number;
};

const extractHour = (item: HourlyMetric): number => {
  const hourFromField = Number(item.hour ?? "");
  if (!Number.isNaN(hourFromField)) return hourFromField;
  if (!item.slot) return 0;
  const date = new Date(item.slot);
  return Number.isNaN(date.getTime()) ? 0 : date.getHours();
};

const aggregateByHour = (data: HourlyMetric[]): Map<number, HourAgg> => {
  const grouped = new Map<number, HourAgg>();

  for (const item of data) {
    const hour = extractHour(item);
    const current = grouped.get(hour) ?? {
      checkout: 0,
      gasto: 0,
      faturamento: 0,
      relacao: 0,
      count: 0,
    };

    current.checkout += Number(item.checkout_conversion ?? 0);
    current.gasto += Number(item.cost ?? 0);
    current.faturamento += Number(item.revenue ?? 0);
    current.relacao += Number(item.roi ?? 0);
    current.count += 1;
    grouped.set(hour, current);
  }

  return grouped;
};

const DashboardGrafico = ({
  hourlyData,
  comparedHourlyData = [],
  isLoading = false,
  period = "24h",
  compareLabel,
}: DashboardGraficoProps) => {
  const isCompareMode = Boolean(compareLabel && comparedHourlyData.length > 0);

  const dadosUnificados = useMemo(() => {
    const baseByHour = aggregateByHour(hourlyData);
    const compareByHour = aggregateByHour(comparedHourlyData);

    return Array.from({ length: HOURS_PER_DAY }, (_, hour) => {
      const base = baseByHour.get(hour);
      const compare = compareByHour.get(hour);
      return {
        xKey: String(hour),
        axisLabel: `${String(hour).padStart(2, "0")}:00`,
        checkout_base: base ? base.checkout : 0,
        gasto_base: base ? base.gasto : 0,
        faturamento_base: base ? base.faturamento : 0,
        relacao_base: base && base.count > 0 ? base.relacao / base.count : 0,
        checkout_compare: compare ? compare.checkout : 0,
        gasto_compare: compare ? compare.gasto : 0,
        faturamento_compare: compare ? compare.faturamento : 0,
        relacao_compare: compare && compare.count > 0 ? compare.relacao / compare.count : 0,
      };
    }).filter((item) => {
      const baseHasData = item.checkout_base || item.gasto_base || item.faturamento_base || item.relacao_base;
      const compareHasData = item.checkout_compare || item.gasto_compare || item.faturamento_compare || item.relacao_compare;
      return Boolean(baseHasData || compareHasData);
    });
  }, [hourlyData, comparedHourlyData]);

  const relacaoValores = dadosUnificados.flatMap((d) => [d.relacao_base, d.relacao_compare]);
  const relacaoMin = Math.min(...relacaoValores, 0);
  const relacaoMax = Math.max(...relacaoValores, 0);
  const relacaoPadding = Math.max((relacaoMax - relacaoMin) * 0.2, 0.2);
  const relacaoBaseMin = relacaoMin < 1 ? relacaoMin - relacaoPadding : 0;
  const relacaoBaseMax = relacaoMax + relacaoPadding;
  const relacaoSpan = Math.max(relacaoBaseMax - relacaoBaseMin, 1);
  // Empurra o piso do eixo para baixo para manter a linha de ROI no topo visual.
  const relacaoDomain: [number, number] = [
    relacaoBaseMin - relacaoSpan * 3,
    relacaoBaseMax,
  ];

  const labelsNegativos = dadosUnificados
    .filter((d) => d.relacao_base < 1)
    .map((d) => d.xKey);

  const nameByKey: Record<string, string> = {
    checkout_base: compareLabel ? `Checkout ${compareLabel.baseDate}` : "Checkout",
    gasto_base: compareLabel ? `Gasto ${compareLabel.baseDate}` : "Gasto",
    faturamento_base: compareLabel ? `Faturamento ${compareLabel.baseDate}` : "Faturamento",
    relacao_base: compareLabel ? `ROI ${compareLabel.baseDate}` : "ROI",
    checkout_compare: compareLabel ? `Checkout ${compareLabel.compareDate}` : "Checkout comparado",
    gasto_compare: compareLabel ? `Gasto ${compareLabel.compareDate}` : "Gasto comparado",
    faturamento_compare: compareLabel ? `Faturamento ${compareLabel.compareDate}` : "Faturamento comparado",
    relacao_compare: compareLabel ? `ROI ${compareLabel.compareDate}` : "ROI comparado",
  };

  const ComparisonTooltip = (props: {
    active?: boolean;
    payload?: Array<{ payload: Record<string, number> }>;
    label?: string | number;
  }) => {
    const { active, payload, label } = props;
    if (!active || !payload || payload.length === 0) return null;

    const row = payload[0]?.payload as {
      checkout_base: number;
      gasto_base: number;
      faturamento_base: number;
      relacao_base: number;
      checkout_compare: number;
      gasto_compare: number;
      faturamento_compare: number;
      relacao_compare: number;
    };

    const hourLabel = `${String(label).padStart(2, "0")}:00`;

    return (
      <div
        style={{
          backgroundColor: "#0f172a",
          border: "1px solid #334155",
          borderRadius: "8px",
          padding: "10px 12px",
          minWidth: "240px",
        }}
      >
        <div style={{ color: "#e2e8f0", fontWeight: 700, marginBottom: "8px" }}>
          Hora: {hourLabel}
        </div>

        <div style={{ color: "#bfdbfe", fontSize: "12px", fontWeight: 600 }}>
          {compareLabel ? `Base (${compareLabel.baseDate})` : "Base"}
        </div>
        <div style={{ color: "#cbd5e1", fontSize: "12px" }}>Checkout: {Number(row.checkout_base || 0).toFixed(2)}%</div>
        <div style={{ color: "#cbd5e1", fontSize: "12px" }}>Gasto: ${Number(row.gasto_base || 0).toFixed(2)}</div>
        <div style={{ color: "#cbd5e1", fontSize: "12px" }}>Faturamento: ${Number(row.faturamento_base || 0).toFixed(2)}</div>
        <div style={{ color: "#cbd5e1", fontSize: "12px", marginBottom: isCompareMode ? "8px" : 0 }}>
          ROI: {Number(row.relacao_base || 0).toFixed(2)}%
        </div>

        {isCompareMode && (
          <>
            <div style={{ color: "rgba(226, 232, 240, 0.75)", fontSize: "12px", fontWeight: 600 }}>
              {compareLabel ? `Comparado (${compareLabel.compareDate})` : "Comparado"}
            </div>
            <div style={{ color: "rgba(203, 213, 225, 0.8)", fontSize: "12px" }}>
              Checkout: {Number(row.checkout_compare || 0).toFixed(2)}%
            </div>
            <div style={{ color: "rgba(203, 213, 225, 0.8)", fontSize: "12px" }}>
              Gasto: ${Number(row.gasto_compare || 0).toFixed(2)}
            </div>
            <div style={{ color: "rgba(203, 213, 225, 0.8)", fontSize: "12px" }}>
              Faturamento: ${Number(row.faturamento_compare || 0).toFixed(2)}
            </div>
            <div style={{ color: "rgba(203, 213, 225, 0.8)", fontSize: "12px" }}>
              ROI: {Number(row.relacao_compare || 0).toFixed(2)}%
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="chartContainer ui-card">
      <div className="chartHeader">
        <div>
          <h2 className="chartTitle">
            Performance Analitica
          </h2>
          <small className="chartSubtitle">
            {isCompareMode && compareLabel
              ? `Comparando ${compareLabel.baseDate} vs ${compareLabel.compareDate}`
              : period === "24h"
                ? "Últimas 24 horas"
                : period === "daily"
                  ? "Hoje"
                  : period === "weekly"
                    ? "Esta semana"
                    : "Este mês"}
          </small>
        </div>
        <div className="chartHeaderControls">
          {isCompareMode && compareLabel && (
            <>
              <span className="compareBadge">Base: {compareLabel.baseDate}</span>
              <span className="compareBadge compareBadge--faded">Comparado: {compareLabel.compareDate}</span>
            </>
          )}
          <small className="chartMeta">
            {isLoading ? "Atualizando..." : `${dadosUnificados.length} pontos`}
          </small>
        </div>
      </div>

      <div className="chartCanvas">
        {dadosUnificados.length === 0 ? (
          <p className="chartEmptyState">
            Sem dados para exibir no grafico.
          </p>
        ) : (
          <>
            <p className="chartDescription">
              {isCompareMode && "Comparativo por hora com dia base e dia comparado"}
              {!isCompareMode && period === "24h" && "Gasto, Faturamento e ROI Por Hora"}
              {!isCompareMode && period === "daily" && "Gasto, Faturamento e ROI Por Hora do Dia"}
              {period === "weekly" && "Gasto, Faturamento e ROI Por Dia da Semana"}
              {period === "monthly" && "Gasto, Faturamento e ROI Por Dia do Mês"}
            </p>
            <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={dadosUnificados}
              barCategoryGap="35%"
              barGap={2}
              margin={{ top: 10, right: 12, left: 0, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="rgba(51, 65, 85, 0.55)"
              />
              <XAxis
                dataKey="xKey"
                tickFormatter={(value) => `${String(value).padStart(2, "0")}:00`}
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                yAxisId="valores"
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis yAxisId="relacao" hide domain={relacaoDomain} />
              <Tooltip
                shared
                content={<ComparisonTooltip />}
              />
              <Legend
                wrapperStyle={{ fontSize: "11px", color: "#94a3b8" }}
                formatter={(value: string) => nameByKey[value] ?? value}
              />
              <Bar
                yAxisId="valores"
                dataKey="checkout_base"
                fill="#f59e0b"
                barSize={8}
                radius={[4, 4, 0, 0]}
              />
              <Bar
                yAxisId="valores"
                dataKey="gasto_base"
                fill="#ef4444"
                barSize={8}
                radius={[4, 4, 0, 0]}
              />
              <Bar
                yAxisId="valores"
                dataKey="faturamento_base"
                fill="#2563eb"
                barSize={8}
                radius={[4, 4, 0, 0]}
              />
              {isCompareMode && (
                <>
                  <Bar yAxisId="valores" dataKey="checkout_compare" fill="#f59e0b" fillOpacity={0.28} barSize={8} radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="valores" dataKey="gasto_compare" fill="#ef4444" fillOpacity={0.28} barSize={8} radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="valores" dataKey="faturamento_compare" fill="#2563eb" fillOpacity={0.28} barSize={8} radius={[4, 4, 0, 0]} />
                </>
              )}
              {labelsNegativos.map((label) => (
                <ReferenceLine
                  key={`neg-${label}`}
                  x={label}
                  stroke="#ef4444"
                  strokeDasharray="3 6"
                  strokeOpacity={0.45}
                />
              ))}
              <Line
                yAxisId="relacao"
                type="monotone"
                dataKey="relacao_base"
                stroke="#22c55e"
                dot={({ cx, cy, payload }) => {
                  const isNegative = Number(payload?.relacao_base ?? 0) < 1;

                  return (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={4}
                      fill={isNegative ? "#ef4444" : "#22c55e"}
                      stroke={isNegative ? "#fee2e2" : "#dcfce7"}
                      strokeWidth={1}
                    />
                  );
                }}
                strokeWidth={2.5}
                activeDot={{ r: 5, strokeWidth: 0 }}
                connectNulls
              />
              {isCompareMode && (
                <Line
                  yAxisId="relacao"
                  type="monotone"
                  dataKey="relacao_compare"
                  stroke="#22c55e"
                  strokeOpacity={0.35}
                  strokeDasharray="5 5"
                  dot={({ cx, cy, payload }) => {
                    const isNegative = Number(payload?.relacao_compare ?? 0) < 1;
                    return (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={3.5}
                        fill={isNegative ? "#ef4444" : "#22c55e"}
                        fillOpacity={0.4}
                        stroke="transparent"
                      />
                    );
                  }}
                  strokeWidth={2}
                  activeDot={{ r: 4, strokeWidth: 0 }}
                  connectNulls
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
          </>
        )}
      </div>
    </div>
  );
};

export default DashboardGrafico;

