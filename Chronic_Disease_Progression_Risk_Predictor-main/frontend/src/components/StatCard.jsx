export default function StatCard({ label, value, note }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value">{value}</div>
      {note ? <div className="stat-card-note">{note}</div> : null}
    </div>
  );
}
