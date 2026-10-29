import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const COLORS = { Low: "#2f8f5b", Medium: "#b9770f", High: "#c1443c" };

export default function RiskDistributionChart({ data }) {
  const safeData = data || [];
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={safeData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e3e7ec" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 13, fill: "#5b6472" }} axisLine={{ stroke: "#e3e7ec" }} tickLine={false} />
        <YAxis tick={{ fontSize: 13, fill: "#5b6472" }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={{ borderRadius: 10, border: "1px solid #e3e7ec", fontSize: 13.5 }}
          cursor={{ fill: "#f4f6f8" }}
        />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={64}>
          {safeData.map((entry, idx) => (
            <Cell key={idx} fill={COLORS[entry.name] || "#0f5c5c"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
