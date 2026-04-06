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
  comparedData?: ConversionBreakdownMetric[];
  isLoading?: boolean;
  compareLabel?: {
    baseDate: string;
    compareDate: string;
  };
}

type ChartRow = {
  label: string;
  initiate_checkout_base: number;
  purchase_base: number;
  conversion_rate_base: number;
  initiate_checkout_compare: number;
  purchase_compare: number;
  conversion_rate_compare: number;
};

const normalizeLabel = (value: string): string => String(value || "unknown").trim() || "unknown";

const ConversionInsightsChart = ({ data, comparedData = [], isLoading = false, compareLabel }: ConversionInsightsChartProps) => {
  const isCompareMode = Boolean(compareLabel && comparedData.length > 0);

  const chartData = useMemo(() => {
    const grouped = new Map<string, Omit<ChartRow, "conversion_rate_base" | "conversion_rate_compare">>();

    for (const row of data) {
      const checkout = normalizeLabel(row.checkout);
      const existing = grouped.get(checkout) ?? {
        label: checkout,
        initiate_checkout_base: 0,
        purchase_base: 0,
        initiate_checkout_compare: 0,
        purchase_compare: 0,
      };

      existing.initiate_checkout_base += Number(row.initiate_checkout || 0);
      existing.purchase_base += Number(row.purchase || 0);
      grouped.set(checkout, existing);
    }

    for (const row of comparedData) {
      const checkout = normalizeLabel(row.checkout);
      const existing = grouped.get(checkout) ?? {
        label: checkout,
        initiate_checkout_base: 0,
        purchase_base: 0,
        initiate_checkout_compare: 0,
        purchase_compare: 0,
      };

      existing.initiate_checkout_compare += Number(row.initiate_checkout || 0);
      existing.purchase_compare += Number(row.purchase || 0);
      grouped.set(checkout, existing);
    }

    const rows = Array.from(grouped.values())
      .map((item) => ({
        ...item,
        conversion_rate_base: item.initiate_checkout_base > 0
          ? (item.purchase_base / item.initiate_checkout_base) * 100
          : 0,
        conversion_rate_compare: item.initiate_checkout_compare > 0
          ? (item.purchase_compare / item.initiate_checkout_compare) * 100
          : 0,
      }))
      .sort((a, b) => b.purchase_base - a.purchase_base || b.initiate_checkout_base - a.initiate_checkout_base);

    return rows;
  }, [data, comparedData]);

  return (
    <section className="conversionChartSection">
      <div className="conversionChartHeader">
        <div>
          <h2 className="sectionTitle">📈 Análise Interativa de Conversão</h2>
          <p className="conversionChartSubtitle">
            Volume por Initiate Checkout, compras e taxa de conversão.
          </p>
          {isCompareMode && compareLabel && (
            <div className="compareLegendRow">
              <span className="compareBadge">Base: {compareLabel.baseDate}</span>
              <span className="compareBadge compareBadge--faded">Comparado: {compareLabel.compareDate}</span>
            </div>
          )}
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
                    if (String(name).startsWith("conversion_rate")) return [`${numeric.toFixed(2)}%`, "Conversão"];
                    if (String(name).startsWith("purchase")) return [numeric.toLocaleString("pt-BR"), "Purchase"];
                    return [numeric.toLocaleString("pt-BR"), "Initiate Checkout"];
                  }}
                  labelFormatter={(label) => `Categoria: ${label}`}
                />
                <Legend
                  wrapperStyle={{ fontSize: "12px", color: "#94a3b8" }}
                  formatter={(value) => {
                    if (value === "initiate_checkout_base") {
                      return compareLabel ? `Initiate Checkout (${compareLabel.baseDate})` : "Initiate Checkout";
                    }
                    if (value === "purchase_base") {
                      return compareLabel ? `Purchase (${compareLabel.baseDate})` : "Purchase";
                    }
                    if (value === "conversion_rate_base") {
                      return compareLabel ? `Conversão (${compareLabel.baseDate})` : "Conversão %";
                    }
                    if (value === "initiate_checkout_compare") {
                      return compareLabel ? `Initiate Checkout (${compareLabel.compareDate})` : "Initiate Checkout comparado";
                    }
                    if (value === "purchase_compare") {
                      return compareLabel ? `Purchase (${compareLabel.compareDate})` : "Purchase comparado";
                    }
                    return compareLabel ? `Conversão (${compareLabel.compareDate})` : "Conversão comparada";
                  }}
                />
                <Bar yAxisId="volume" dataKey="initiate_checkout_base" fill="#3b82f6" radius={[6, 6, 0, 0]} />
                <Bar yAxisId="volume" dataKey="purchase_base" fill="#22c55e" radius={[6, 6, 0, 0]} />
                {isCompareMode && (
                  <>
                    <Bar yAxisId="volume" dataKey="initiate_checkout_compare" fill="#3b82f6" fillOpacity={0.28} radius={[6, 6, 0, 0]} />
                    <Bar yAxisId="volume" dataKey="purchase_compare" fill="#22c55e" fillOpacity={0.28} radius={[6, 6, 0, 0]} />
                  </>
                )}
                <Line
                  yAxisId="rate"
                  type="monotone"
                  dataKey="conversion_rate_base"
                  stroke="#f59e0b"
                  strokeWidth={2.5}
                  dot={{ fill: "#f59e0b", r: 4 }}
                  activeDot={{ r: 6 }}
                />
                {isCompareMode && (
                  <Line
                    yAxisId="rate"
                    type="monotone"
                    dataKey="conversion_rate_compare"
                    stroke="#f59e0b"
                    strokeOpacity={0.4}
                    strokeDasharray="5 5"
                    strokeWidth={2}
                    dot={{ fill: "#f59e0b", fillOpacity: 0.4, r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </section>
  );
};

export default ConversionInsightsChart;

