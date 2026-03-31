import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer } from "recharts";
import type { HourlyMetric } from "../utils/reqs.ts";

interface SparklineCardProps {
  data: HourlyMetric[];
  metric: "cost" | "revenue" | "profit" | "roi";
  label: string;
}

/**
 * Mini sparkline chart para mostrar tendência em um card
 * Exemplo de uso:
 * <SparklineCard
 *   data={hourlyData}
 *   metric="revenue"
 *   label="Faturamento"
 * />
 */
export const SparklineCard = ({ data, metric, label }: SparklineCardProps) => {
  const sparklineData = data.slice(-12).map((item, idx) => ({
    id: idx,
    value: Number(item[metric] ?? 0),
  }));

  const min = Math.min(...sparklineData.map((d) => d.value));
  const max = Math.max(...sparklineData.map((d) => d.value));
  const isIncreasing = sparklineData[sparklineData.length - 1].value >= sparklineData[0].value;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      <small style={{ color: "#9ca3af", fontSize: "11px" }}>{label}</small>
      <div style={{ width: "100%", height: "40px" }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sparklineData} margin={{ top: 2, right: 2, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`sparkline-${metric}`} x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={isIncreasing ? "#10b981" : "#ef4444"}
                  stopOpacity={0.3}
                />
                <stop
                  offset="95%"
                  stopColor={isIncreasing ? "#10b981" : "#ef4444"}
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>
            <XAxis dataKey="id" hide />
            <YAxis hide domain={[min, max]} />
            <Area
              type="monotone"
              dataKey="value"
              stroke={isIncreasing ? "#10b981" : "#ef4444"}
              fill={`url(#sparkline-${metric})`}
              strokeWidth={1.5}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default SparklineCard;

