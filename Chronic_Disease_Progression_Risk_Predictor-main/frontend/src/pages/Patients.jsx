import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import TopBar from "../components/TopBar.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import LoadingRow from "../components/LoadingRow.jsx";
import EmptyState from "../components/EmptyState.jsx";
import { getPatients } from "../services/api.js";

function formatDate(value) {
  if (!value) return "\u2014";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function Patients() {
  const [patients, setPatients] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [filters, setFilters] = useState({ risk: "", gender: "", search: "", page: 1 });

  const load = useCallback(async (params) => {
    setLoading(true);
    try {
      const query = { page: params.page, limit: 25 };
      if (params.risk) query.risk = params.risk;
      if (params.gender) query.gender = params.gender;
      if (params.search) query.search = params.search;
      const data = await getPatients(query);
      setPatients(data.patients);
      setPagination(data.pagination);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.error || "Could not load patients.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.risk, filters.gender, filters.page]);

  const applySearch = (e) => {
    e.preventDefault();
    setFilters((f) => ({ ...f, page: 1 }));
    load({ ...filters, page: 1 });
  };

  return (
    <>
      <TopBar title="Patients" subtitle={pagination ? `${pagination.total.toLocaleString()} patients in the cohort` : ""} />
      <div className="content">
        <form className="filter-bar" onSubmit={applySearch}>
          <input
            className="input"
            placeholder="Search patient ID\u2026"
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
            style={{ minWidth: 220 }}
          />
          <select
            className="select"
            value={filters.risk}
            onChange={(e) => setFilters((f) => ({ ...f, risk: e.target.value, page: 1 }))}
          >
            <option value="">Any risk level</option>
            <option value="HIGH">High risk</option>
            <option value="MEDIUM">Medium risk</option>
            <option value="LOW">Low risk</option>
          </select>
          <select
            className="select"
            value={filters.gender}
            onChange={(e) => setFilters((f) => ({ ...f, gender: e.target.value, page: 1 }))}
          >
            <option value="">Any gender</option>
            <option value="M">Male</option>
            <option value="F">Female</option>
          </select>
          <button className="btn btn-secondary" type="submit">
            Search
          </button>
        </form>

        <div className="card" style={{ padding: 0 }}>
          {loading ? (
            <div style={{ padding: 20 }}>
              <LoadingRow />
            </div>
          ) : error ? (
            <div style={{ padding: 20 }}>
              <EmptyState title="Couldn't load patients" description={error} />
            </div>
          ) : patients.length === 0 ? (
            <div style={{ padding: 20 }}>
              <EmptyState
                title="No patients found"
                description="Import patient CSV data via the backend seed pipeline, then run a risk assessment."
              />
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Patient ID</th>
                    <th>Age</th>
                    <th>Gender</th>
                    <th>Chronic Conditions</th>
                    <th>Acute Risk</th>
                    <th>Progression Risk</th>
                    <th>Last Encounter</th>
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
                      <td>{p.age ?? "\u2014"}</td>
                      <td>{p.gender || "\u2014"}</td>
                      <td>
                        {p.chronicConditions?.length ? (
                          <span className="text-muted">
                            {p.chronicConditions.slice(0, 2).join(", ")}
                            {p.chronicConditions.length > 2 ? ` +${p.chronicConditions.length - 2}` : ""}
                          </span>
                        ) : (
                          <span className="text-faint">None recorded</span>
                        )}
                      </td>
                      <td>
                        <RiskBadge level={p.acuteRisk} probability={p.acuteProbability} />
                      </td>
                      <td>
                        <RiskBadge level={p.progressionRisk} probability={p.progressionProbability} />
                      </td>
                      <td className="text-muted">{formatDate(p.lastEncounter)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {pagination && pagination.pages > 1 && (
          <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 16 }}>
            <button
              className="btn btn-secondary"
              disabled={pagination.page <= 1}
              onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}
            >
              Previous
            </button>
            <span className="text-muted" style={{ alignSelf: "center", fontSize: 13 }}>
              Page {pagination.page} of {pagination.pages}
            </span>
            <button
              className="btn btn-secondary"
              disabled={pagination.page >= pagination.pages}
              onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </>
  );
}
