export default function RiskBadge({ level, probability }) {
  const tier = level ? level.toUpperCase() : "NONE";
  const label = tier === "NONE" ? "Not scored" : tier;
  return (
    <span className={`risk-badge ${tier}`}>
      <span className="risk-badge-dot" />
      {label}
      {probability !== undefined && probability !== null ? ` \u00b7 ${(probability * 100).toFixed(1)}%` : ""}
    </span>
  );
}
