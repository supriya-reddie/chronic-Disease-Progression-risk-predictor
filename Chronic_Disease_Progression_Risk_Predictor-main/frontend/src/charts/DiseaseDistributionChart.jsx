import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function DiseaseDistributionChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="text-muted" style={{ padding: "24px 0" }}>No chronic condition data available yet.</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, data.length * 34)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e3e7ec" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 13, fill: "#5b6472" }} axisLine={false} tickLine={false} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="name"
          width={190}
          tick={{ fontSize: 13, fill: "#10151f" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e3e7ec", fontSize: 13.5 }} cursor={{ fill: "#f4f6f8" }} />
        <Bar dataKey="value" fill="#0f5c5c" radius={[0, 6, 6, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}
