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

const MAX_CHART_POINTS = 24;

interface DashboardGraficoProps {
  hourlyData: HourlyMetric[];
  isLoading?: boolean;
  selectedSquad: string;
  period?: "24h" | "daily" | "weekly" | "monthly";
}

// Agrupa dados por período
const aggregateByPeriod = (data: HourlyMetric[], period: "24h" | "daily" | "weekly" | "monthly"): HourlyMetric[] => {
  const grouped: Map<string, HourlyMetric> = new Map();

  data.forEach((item) => {
    let key: string;

    if (period === "24h" || period === "daily") {
      // Para 24h e daily, agrupa por data+hora sem ajuste manual de timezone.
      const day = item.slot ? String(item.slot).slice(0, 10) : "unknown-day";
      const hour = String(item.hour ?? "0").padStart(2, "0");
      key = `${day}_${hour}`;
    } else if (period === "weekly") {
      // Agrupa por dia da semana
      const date = item.slot ? new Date(item.slot) : new Date();
      const day = date.toLocaleDateString("pt-BR", { weekday: "long", month: "2-digit", day: "2-digit" });
      key = day;
    } else {
      // monthly - agrupa por dia
      const date = item.slot ? new Date(item.slot) : new Date();
      const day = date.toLocaleDateString("pt-BR", { month: "2-digit", day: "2-digit" });
      key = day;
    }

    if (grouped.has(key)) {
      const existing = grouped.get(key)!;
      grouped.set(key, {
        ...existing,
        cost: (existing.cost ?? 0) + (item.cost ?? 0),
        profit: (existing.profit ?? 0) + (item.profit ?? 0),
        revenue: (existing.revenue ?? 0) + (item.revenue ?? 0),
        checkout_conversion: (existing.checkout_conversion ?? 0) + (item.checkout_conversion ?? 0),
        roi: existing.roi !== 0 ? (existing.roi + item.roi) / 2 : item.roi, // ROI média
      });
    } else {
      grouped.set(key, { ...item });
    }
  });

  return Array.from(grouped.values());
};

const DashboardGrafico = ({
  hourlyData,
  isLoading = false,
  period = "24h",
}: DashboardGraficoProps) => {
  // Agregar dados baseado no período
  const aggregatedData = useMemo(() => aggregateByPeriod(hourlyData, period), [hourlyData, period]);

  // Função para gerar chave consistente para cada período
  const getConsistentKey = (item: HourlyMetric, period: "24h" | "daily" | "weekly" | "monthly"): string => {
    if (period === "24h" || period === "daily") {
      const day = item.slot ? String(item.slot).slice(0, 10) : "unknown-day";
      const hour = String(item.hour ?? "0").padStart(2, "0");
      return `${day}_${hour}`;
    } else if (period === "weekly") {
      const date = item.slot ? new Date(`${String(item.slot).slice(0, 10)}T12:00:00`) : new Date();
      return date.toLocaleDateString("pt-BR", { weekday: "long", month: "2-digit", day: "2-digit" });
    } else {
      const date = item.slot ? new Date(`${String(item.slot).slice(0, 10)}T12:00:00`) : new Date();
      return date.toLocaleDateString("pt-BR", { month: "2-digit", day: "2-digit" });
    }
  };

  const dadosUnificados = useMemo(
    () => {
      const shiftHourForward = (hourValue: string | number | null | undefined): number => {
        const parsedHour = Number(hourValue ?? 0);

        if (Number.isNaN(parsedHour)) {
          return 0;
        }

        return (parsedHour + 1 + 24) % 24;
      };

      const shiftSlotForward = (slotValue: string): Date | null => {
        const parsed = new Date(slotValue);
        if (Number.isNaN(parsed.getTime())) {
          return null;
        }

        return new Date(parsed.getTime() + 60 * 60 * 1000);
      };

      const getOrderValue = (item: HourlyMetric): number => {
        if (item.slot) {
          const parsed = Date.parse(item.slot);

          if (!Number.isNaN(parsed)) {
            return parsed;
          }
        }

        return Number(item.hour || 0);
      };

      const getAxisLabel = (item: HourlyMetric): string => {
        if (period !== "24h" && period !== "daily" && item.slot) {
          const date = new Date(item.slot);
          if (period === "weekly") {
            return date.toLocaleDateString("pt-BR", { weekday: "short", month: "2-digit", day: "2-digit" });
          } else {
            return date.toLocaleDateString("pt-BR", { month: "2-digit", day: "2-digit" });
          }
        }
        const hourLabel = String(shiftHourForward(item.hour)).padStart(2, "0");
        return `${hourLabel}:00`;
      };

      const getTooltipLabel = (item: HourlyMetric): string => {
        if (!item.slot) {
          return getAxisLabel(item);
        }

        const parsed = period === "24h" || period === "daily"
          ? shiftSlotForward(item.slot)
          : new Date(item.slot);

        if (!parsed) {
          return item.slot;
        }

        if (Number.isNaN(parsed.getTime())) {
          return item.slot;
        }

        if (period === "24h" || period === "daily") {
          return parsed.toLocaleString("pt-BR", {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          });
        } else {
          return parsed.toLocaleString("pt-BR", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
          });
        }
      };

      return [...aggregatedData]
        .sort((a, b) => getOrderValue(a) - getOrderValue(b))
        .slice(0, MAX_CHART_POINTS)
        .map((item) => {
          const relacao = Number(item.roi ?? 0);
          // Usar a chave consistente para xKey também
          const xKey = getConsistentKey(item, period);

          return {
            xKey,
            axisLabel: getAxisLabel(item),
            tooltipLabel: getTooltipLabel(item),
            checkout: Number(item.checkout_conversion ?? 0),
            faturamento: Number(item.revenue ?? 0),
            gasto: Number(item.cost ?? 0),
            relacao,
          };
        });
    },
    [aggregatedData, period],
  );

  const relacaoValores = dadosUnificados.map((d) => d.relacao);
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
    .filter((d) => d.relacao < 1)
    .map((d) => d.xKey);

  const tooltipLabels = useMemo(
    () => new Map(dadosUnificados.map((item) => [item.xKey, item.tooltipLabel])),
    [dadosUnificados],
  );

  return (
    <div className="chartContainer ui-card">
      <div className="chartHeader">
        <div>
          <h2 className="chartTitle">
            Performance Analitica
          </h2>
          <small className="chartSubtitle">
            {period === "24h" && "Últimas 24 horas"}
            {period === "daily" && "Hoje"}
            {period === "weekly" && "Esta semana"}
            {period === "monthly" && "Este mês"}
          </small>
        </div>
        <div className="chartHeaderControls">
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
              {period === "24h" && "Gasto, Faturamento e ROI Por Hora"}
              {period === "daily" && "Gasto, Faturamento e ROI Por Hora do Dia"}
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
                tickFormatter={(value) => {
                  const entry = dadosUnificados.find((item) => item.xKey === value);
                  return entry?.axisLabel ?? String(value);
                }}
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
                shared={false}
                labelFormatter={(value) => tooltipLabels.get(String(value)) ?? String(value)}
                contentStyle={{
                  backgroundColor: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                }}
                formatter={(value, key) => {
                  const numericValue = Array.isArray(value)
                    ? Number(value[0] ?? 0)
                    : Number(value ?? 0);

                  if (key === "relacao") {
                    return [numericValue.toFixed(4), "ROI"];
                  }

                  if (key === "gasto") {
                    return [`$${numericValue.toFixed(2)}`, "Gasto"];
                  }

                  if (key === "checkout") {
                    return [`${numericValue.toFixed(2)}%`, "Checkout Conversion"];
                  }

                  return [`$${numericValue.toFixed(2)}`, "Faturamento"];
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: "11px", color: "#94a3b8" }}
                formatter={(value: string) => {
                  if (value === "checkout") return "Checkout";
                  if (value === "gasto") return "Gasto";
                  if (value === "faturamento") return "Faturamento";
                  return "ROI";
                }}
              />
              <Bar
                yAxisId="valores"
                dataKey="checkout"
                fill="#f59e0b"
                barSize={8}
                radius={[4, 4, 0, 0]}
              />
              <Bar
                yAxisId="valores"
                dataKey="gasto"
                fill="#ef4444"
                barSize={8}
                radius={[4, 4, 0, 0]}
              />
              <Bar
                yAxisId="valores"
                dataKey="faturamento"
                fill="#2563eb"
                barSize={8}
                radius={[4, 4, 0, 0]}
              />
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
                dataKey="relacao"
                stroke="#22c55e"
                dot={({ cx, cy, payload }) => {
                  const isNegative = Number(payload?.relacao ?? 0) < 1;

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
            </ComposedChart>
          </ResponsiveContainer>
          </>
        )}
      </div>
    </div>
  );
};

export default DashboardGrafico;

