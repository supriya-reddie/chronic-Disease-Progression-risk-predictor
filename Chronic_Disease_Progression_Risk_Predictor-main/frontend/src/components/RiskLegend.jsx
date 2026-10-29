export default function RiskLegend({ title = "What do these risk levels mean?" }) {
  return (
    <div className="risk-legend">
      <div className="card-title" style={{ fontSize: 14.5 }}>
        {title}
      </div>
      <div className="risk-legend-row">
        <span className="risk-badge LOW">
          <span className="risk-badge-dot" />
          Low
        </span>
        <span className="desc">Continue routine monitoring. No action needed right now.</span>
      </div>
      <div className="risk-legend-row">
        <span className="risk-badge MEDIUM">
          <span className="risk-badge-dot" />
          Medium
        </span>
        <span className="desc">Worth a closer look. Consider scheduling a check-in or follow-up.</span>
      </div>
      <div className="risk-legend-row">
        <span className="risk-badge HIGH">
          <span className="risk-badge-dot" />
          High
        </span>
        <span className="desc">Needs attention soon. Recommended for care-manager outreach.</span>
      </div>
    </div>
  );
}
