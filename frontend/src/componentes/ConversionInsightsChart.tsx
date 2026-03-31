import { useMemo, useState } from "react";
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

type GroupBy = "checkout" | "product" | "squad" | "selection";

type ChartRow = {
  label: string;
  groupBy: GroupBy;
  initiate_checkout: number;
  purchase: number;
  conversion_rate: number;
  volume: number;
};

const FILTER_ALL = "__all__";

const normalizeLabel = (value: string): string => String(value || "unknown").trim() || "unknown";
const normalizeKey = (value: string): string => normalizeLabel(value).toLowerCase();

type DimensionMaps = {
  checkout: Map<string, string>;
  squad: Map<string, string>;
  product: Map<string, string>;
};

const getSortedOptions = (map: Map<string, string>) =>
  [FILTER_ALL, ...Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1], "pt-BR")).map(([key]) => key)];

const ConversionInsightsChart = ({ data, isLoading = false }: ConversionInsightsChartProps) => {
  const [selectedCheckout, setSelectedCheckout] = useState<string>(FILTER_ALL);
  const [selectedSquad, setSelectedSquad] = useState<string>(FILTER_ALL);
  const [selectedProduct, setSelectedProduct] = useState<string>(FILTER_ALL);

  const dimensionMaps = useMemo<DimensionMaps>(() => {
    const maps: DimensionMaps = {
      checkout: new Map<string, string>(),
      squad: new Map<string, string>(),
      product: new Map<string, string>(),
    };

    for (const row of data) {
      const checkoutKey = normalizeKey(row.checkout);
      const squadKey = normalizeKey(row.squad);
      const productKey = normalizeKey(row.product);

      if (!maps.checkout.has(checkoutKey)) maps.checkout.set(checkoutKey, normalizeLabel(row.checkout));
      if (!maps.squad.has(squadKey)) maps.squad.set(squadKey, normalizeLabel(row.squad));
      if (!maps.product.has(productKey)) maps.product.set(productKey, normalizeLabel(row.product));
    }

    return maps;
  }, [data]);

  const checkoutOptions = useMemo(() => getSortedOptions(dimensionMaps.checkout), [dimensionMaps.checkout]);
  const squadOptions = useMemo(() => getSortedOptions(dimensionMaps.squad), [dimensionMaps.squad]);
  const productOptions = useMemo(() => getSortedOptions(dimensionMaps.product), [dimensionMaps.product]);

  const filteredRows = useMemo(
    () =>
      data.filter((row) => {
        const squad = normalizeKey(row.squad);
        const product = normalizeKey(row.product);
        const checkoutKey = normalizeKey(row.checkout);

        const checkoutMatch = selectedCheckout === FILTER_ALL || checkoutKey === selectedCheckout;
        const squadMatch = selectedSquad === FILTER_ALL || squad === selectedSquad;
        const productMatch = selectedProduct === FILTER_ALL || product === selectedProduct;

        return checkoutMatch && squadMatch && productMatch;
      }),
    [data, selectedCheckout, selectedSquad, selectedProduct],
  );

  const groupBy: GroupBy = useMemo(() => {
    if (selectedCheckout === FILTER_ALL) return "checkout";
    if (selectedProduct === FILTER_ALL) return "product";
    if (selectedSquad === FILTER_ALL) return "squad";
    return "selection";
  }, [selectedCheckout, selectedProduct, selectedSquad]);

  const chartData = useMemo(() => {
    const grouped = new Map<string, ChartRow>();

    const getLabel = (row: ConversionBreakdownMetric): string => {
      if (groupBy === "checkout") return dimensionMaps.checkout.get(normalizeKey(row.checkout)) || normalizeLabel(row.checkout);
      if (groupBy === "product") return dimensionMaps.product.get(normalizeKey(row.product)) || normalizeLabel(row.product);
      if (groupBy === "squad") return dimensionMaps.squad.get(normalizeKey(row.squad)) || normalizeLabel(row.squad);
      return "Seleção atual";
    };

    for (const row of filteredRows) {
      const label = getLabel(row);
      const existing = grouped.get(label) ?? {
        label,
        groupBy,
        initiate_checkout: 0,
        purchase: 0,
        conversion_rate: 0,
        volume: 0,
      };

      existing.initiate_checkout += Number(row.initiate_checkout || 0);
      existing.purchase += Number(row.purchase || 0);
      existing.volume += Number(row.initiate_checkout || 0);
      grouped.set(label, existing);
    }

    const rows = Array.from(grouped.values())
      .map((item) => ({
        ...item,
        conversion_rate: item.initiate_checkout > 0 ? (item.purchase / item.initiate_checkout) * 100 : 0,
      }))
      .sort((a, b) => b.purchase - a.purchase || b.initiate_checkout - a.initiate_checkout)
      .slice(0, 12);

    return rows;
  }, [filteredRows, groupBy, dimensionMaps.checkout, dimensionMaps.product, dimensionMaps.squad]);

  const labelForOption = (kind: keyof DimensionMaps, key: string): string => {
    if (key === FILTER_ALL) return "Todos";
    return dimensionMaps[kind].get(key) || key;
  };

  return (
    <section className="conversionChartSection">
      <div className="conversionChartHeader">
        <div>
          <h2 className="sectionTitle">📈 Análise Interativa de Conversão</h2>
          <p className="conversionChartSubtitle">
            Volume por Initiate Checkout, compras e taxa de conversão com filtros combináveis.
          </p>
        </div>
        <div className="conversionChartFilters">
          <label>
            Checkout
            <select value={selectedCheckout} onChange={(event) => setSelectedCheckout(event.target.value)}>
              {checkoutOptions.map((option) => (
                <option key={`checkout-${option}`} value={option}>
                  {labelForOption("checkout", option)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Squad
            <select value={selectedSquad} onChange={(event) => setSelectedSquad(event.target.value)}>
              {squadOptions.map((option) => (
                <option key={`squad-${option}`} value={option}>
                  {labelForOption("squad", option)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Produto
            <select value={selectedProduct} onChange={(event) => setSelectedProduct(event.target.value)}>
              {productOptions.map((option) => (
                <option key={`product-${option}`} value={option}>
                  {labelForOption("product", option)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="conversionChartCard">
        {isLoading ? (
          <p className="conversionChartEmpty">Carregando dados de conversão...</p>
        ) : chartData.length === 0 ? (
          <p className="conversionChartEmpty">Nenhum dado encontrado para os filtros aplicados</p>
        ) : (
          <div className="conversionChartCanvas">
            <ResponsiveContainer width="100%" height="100%">
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

