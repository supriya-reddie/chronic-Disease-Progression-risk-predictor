import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import TopBar from "../components/TopBar.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import LoadingRow from "../components/LoadingRow.jsx";
import EmptyState from "../components/EmptyState.jsx";
import { getHighRiskPatients } from "../services/api.js";

function formatDate(value) {
  if (!value) return "\u2014";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function HighRiskPatients() {
  const [patients, setPatients] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await getHighRiskPatients();
        setPatients(data.patients);
        setError(null);
      } catch (err) {
        setError(err.response?.data?.error || "Could not load high-risk patients.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <>
      <TopBar title="High-Risk Patients" subtitle="Patients flagged HIGH on acute or progression risk, sorted by probability" />
      <div className="content">
        {loading ? (
          <LoadingRow />
        ) : error ? (
          <EmptyState title="Couldn't load high-risk patients" description={error} />
        ) : patients.length === 0 ? (
          <EmptyState title="No high-risk patients" description="Run a risk assessment to populate this list." />
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Patient</th>
                    <th>Acute Risk</th>
                    <th>Progression Risk</th>
                    <th>Main Driver</th>
                    <th>Last Encounter</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {patients.map((p) => (
                    <tr key={p.patientId}>
                      <td>
                        <Link to={`/patients/${p.patientId}`} className="mono" style={{ color: "var(--brand-dark)", fontWeight: 600 }}>
                          {p.patientId.slice(0, 10)}&hellip;
                        </Link>
                      </td>
                      <td>
                        <RiskBadge level={p.acuteRisk} probability={p.acuteProbability} />
                      </td>
                      <td>
                        <RiskBadge level={p.progressionRisk} probability={p.progressionProbability} />
                      </td>
                      <td className="text-muted">{p.mainDriver}</td>
                      <td className="text-muted">{formatDate(p.lastEncounter)}</td>
                      <td>
                        <Link to={`/patients/${p.patientId}`} className="btn btn-secondary" style={{ padding: "5px 12px", fontSize: 12.5 }}>
                          Review
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
