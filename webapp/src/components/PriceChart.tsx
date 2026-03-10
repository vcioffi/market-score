import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { PricePoint } from "../types/api";

interface PriceChartProps {
  series: PricePoint[];
}

export function PriceChart({ series }: PriceChartProps) {
  return (
    <section className="panel chart-panel">
      <div className="panel-header">
        <h3>Price History</h3>
      </div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={series} margin={{ top: 12, right: 16, left: 0, bottom: 8 }}>
            <defs>
              <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0d9488" stopOpacity={0.45} />
                <stop offset="95%" stopColor="#0d9488" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2a44" />
            <XAxis dataKey="date" tick={{ fill: "#a8b4d6", fontSize: 12 }} />
            <YAxis tick={{ fill: "#a8b4d6", fontSize: 12 }} width={72} />
            <Tooltip
              contentStyle={{
                background: "#0e1528",
                border: "1px solid #263657",
                borderRadius: 12,
                color: "#e9efff",
              }}
            />
            <Area type="monotone" dataKey="close" stroke="#14b8a6" fill="url(#priceFill)" strokeWidth={2.2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
