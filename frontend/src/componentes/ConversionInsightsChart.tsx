import { useMemo } from "react";
import {
  Bar,
  ComposedChart,
  CartesianGrid,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ConversionBreakdownMetric } from "../utils/reqs";

interface ConversionInsightsChartProps {
  data: ConversionBreakdownMetric[];
  isLoading?: boolean;
}

type ChartRow = {
  label: string;
  initiate_checkout: number;
  purchase: number;
  conversion_rate: number;
  volume: number;
};

const normalizeLabel = (value: string): string => String(value || "unknown").trim() || "unknown";

const ConversionInsightsChart = ({ data, isLoading = false }: ConversionInsightsChartProps) => {
  // Agrupar por checkout como padrão
  const chartData = useMemo(() => {
    const grouped = new Map<string, ChartRow>();

    for (const row of data) {
      const checkout = normalizeLabel(row.checkout);
      const existing = grouped.get(checkout) ?? {
        label: checkout,
        initiate_checkout: 0,
        purchase: 0,
        conversion_rate: 0,
        volume: 0,
      };

      existing.initiate_checkout += Number(row.initiate_checkout || 0);
      existing.purchase += Number(row.purchase || 0);
      existing.volume += Number(row.initiate_checkout || 0);
      grouped.set(checkout, existing);
    }

    const rows = Array.from(grouped.values())
      .map((item) => ({
        ...item,
        conversion_rate: item.initiate_checkout > 0 ? (item.purchase / item.initiate_checkout) * 100 : 0,
      }))
      .sort((a, b) => b.purchase - a.purchase || b.initiate_checkout - a.initiate_checkout);

    return rows;
  }, [data]);

  return (
    <section className="conversionChartSection">
      <div className="conversionChartHeader">
        <div>
          <h2 className="sectionTitle">📈 Análise Interativa de Conversão</h2>
          <p className="conversionChartSubtitle">
            Volume por Initiate Checkout, compras e taxa de conversão.
          </p>
        </div>
      </div>

      <div className="conversionChartCard">
        {isLoading && chartData.length === 0 ? (
          <p className="conversionChartEmpty">Carregando dados de conversão...</p>
        ) : chartData.length === 0 ? (
          <p className="conversionChartEmpty">Nenhum dado encontrado para os filtros aplicados</p>
        ) : (
          <div className="conversionChartCanvas">
            <ResponsiveContainer width="100%" height={360} minWidth={0} minHeight={320}>
              <ComposedChart data={chartData} margin={{ top: 12, right: 18, left: 6, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(51, 65, 85, 0.55)" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  yAxisId="volume"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="rate"
                  orientation="right"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  tickFormatter={(value) => `${Number(value).toFixed(0)}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                  }}
                  formatter={(value, name) => {
                    const numeric = Number(value || 0);
                    if (name === "conversion_rate") return [`${numeric.toFixed(2)}%`, "Conversão"];
                    if (name === "purchase") return [numeric.toLocaleString("pt-BR"), "Purchase"];
                    return [numeric.toLocaleString("pt-BR"), "Initiate Checkout"];
                  }}
                  labelFormatter={(label) => `Categoria: ${label}`}
                />
                <Legend
                  wrapperStyle={{ fontSize: "12px", color: "#94a3b8" }}
                  formatter={(value) => {
                    if (value === "initiate_checkout") return "Initiate Checkout";
                    if (value === "purchase") return "Purchase";
                    return "Conversão %";
                  }}
                />
                <Bar yAxisId="volume" dataKey="initiate_checkout" fill="#3b82f6" radius={[6, 6, 0, 0]} />
                <Bar yAxisId="volume" dataKey="purchase" fill="#22c55e" radius={[6, 6, 0, 0]} />
                <Line
                  yAxisId="rate"
                  type="monotone"
                  dataKey="conversion_rate"
                  stroke="#f59e0b"
                  strokeWidth={2.5}
                  dot={{ fill: "#f59e0b", r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </section>
  );
};

export default ConversionInsightsChart;

