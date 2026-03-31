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
import { RechartsDevtools } from "@recharts/devtools";
import type { HourlyMetric, SquadOption } from "../utils/reqs.ts";

const MAX_CHART_POINTS = 24;

interface DashboardGraficoProps {
  hourlyData: HourlyMetric[];
  isLoading?: boolean;
  selectedSquad: string;
  squadOptions: SquadOption[];
  onSquadChange: (value: string) => void;
}

const DashboardGrafico = ({
  hourlyData,
  isLoading = false,
  selectedSquad,
  squadOptions,
  onSquadChange,
}: DashboardGraficoProps) => {
  const dadosUnificados = useMemo(
    () => {
      const shiftHourForward = (hourValue: string | number | null | undefined): number => {
        const parsedHour = Number(hourValue ?? 0);

        if (Number.isNaN(parsedHour)) {
          return 0;
        }

        return (parsedHour + 1 + 24) % 24;
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
        const hourLabel = String(shiftHourForward(item.hour)).padStart(2, "0");
        return `${hourLabel}:00`;
      };

      const getTooltipLabel = (item: HourlyMetric): string => {
        if (!item.slot) {
          return getAxisLabel(item);
        }

        const parsed = new Date(item.slot);
        if (Number.isNaN(parsed.getTime())) {
          return item.slot;
        }

        parsed.setHours(parsed.getHours() + 1);

        return parsed.toLocaleString("pt-BR", {
          day: "2-digit",
          month: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        });
      };

      return [...hourlyData]
        .sort((a, b) => getOrderValue(a) - getOrderValue(b))
        .slice(0, MAX_CHART_POINTS)
        .map((item, index) => {
          const relacao = Number(item.roi ?? 0);
          const shiftedHour = String(shiftHourForward(item.hour)).padStart(2, "0");
          const xKey = item.slot || `${shiftedHour}-${index}`;

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
    [hourlyData],
  );

  const relacaoValores = dadosUnificados.map((d) => d.relacao);
  const relacaoMin = Math.min(...relacaoValores, 0);
  const relacaoMax = Math.max(...relacaoValores, 0);
  const relacaoPadding = Math.max((relacaoMax - relacaoMin) * 0.2, 0.2);
  const relacaoBaseMin = relacaoMin < 0 ? relacaoMin - relacaoPadding : 0;
  const relacaoBaseMax = relacaoMax + relacaoPadding;
  const relacaoSpan = Math.max(relacaoBaseMax - relacaoBaseMin, 1);
  // Empurra o piso do eixo para baixo para manter a linha de ROI no topo visual.
  const relacaoDomain: [number, number] = [
    relacaoBaseMin - relacaoSpan * 3,
    relacaoBaseMax,
  ];

  const labelsNegativos = dadosUnificados
    .filter((d) => d.relacao < 0)
    .map((d) => d.xKey);

  const tooltipLabels = useMemo(
    () => new Map(dadosUnificados.map((item) => [item.xKey, item.tooltipLabel])),
    [dadosUnificados],
  );

  return (
    <div
      style={{
        width: "100%",
        maxWidth: "980px",
        margin: "12px auto",
        background: "#01091a",
        padding: "clamp(12px, 2.5vw, 20px)",
        borderRadius: "12px",
        color: "white",
        fontFamily: "sans-serif",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          marginBottom: "16px",
          gap: "12px",
        }}
      >
        <div>
          <h2 style={{ fontSize: "clamp(14px, 2.8vw, 16px)", margin: 0 }}>
            Performance Analitica
          </h2>
          <small style={{ color: "#9ca3af" }}>Ultimas 24 horas</small>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            flexWrap: "wrap",
            justifyContent: "flex-end",
            width: "100%",
            maxWidth: "420px",
          }}
        >
          <small style={{ color: "#9ca3af" }}>
            {isLoading ? "Atualizando..." : `${dadosUnificados.length} pontos`}
          </small>
          <select
            value={selectedSquad}
            onChange={(event) => onSquadChange(event.target.value)}
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
            {squadOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ width: "100%", height: "clamp(240px, 52vw, 360px)" }}>
        <p
          style={{
            fontSize: "12px",
            color: "#2563eb",
            marginBottom: "5px",
            fontWeight: "bold",
          }}
        >
          Gasto, Faturamento e ROI Por Hora.
        </p>
        {dadosUnificados.length === 0 ? (
          <p style={{ fontSize: "12px", color: "#9ca3af" }}>
            Sem dados para exibir no grafico.
          </p>
        ) : (
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
                stroke="#1f2937"
              />
              <XAxis
                dataKey="xKey"
                tickFormatter={(value) => {
                  const entry = dadosUnificados.find((item) => item.xKey === value);
                  return entry?.axisLabel ?? String(value);
                }}
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                yAxisId="valores"
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis yAxisId="relacao" hide domain={relacaoDomain} />
              <Tooltip
                shared={false}
                labelFormatter={(value) => tooltipLabels.get(String(value)) ?? String(value)}
                contentStyle={{
                  backgroundColor: "#111827",
                  border: "1px solid #1f2937",
                  borderRadius: "8px",
                }}
                formatter={(value, key) => {
                  const numericValue = Array.isArray(value)
                    ? Number(value[0] ?? 0)
                    : Number(value ?? 0);

                  if (key === "relacao") {
                    return [`${numericValue.toFixed(2)}x`, "ROI"];
                  }

                  if (key === "gasto") {
                    return [`$${numericValue.toFixed(2)}`, "Gasto"];
                  }

                  if (key === "checkout") {
                    return [numericValue.toFixed(2), "Checkout Conversion"];
                  }

                  return [`$${numericValue.toFixed(2)}`, "Faturamento"];
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: "11px", color: "#9ca3af" }}
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
              <RechartsDevtools />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default DashboardGrafico;

