import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import TopBar from "../components/TopBar.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import LoadingRow from "../components/LoadingRow.jsx";
import EmptyState from "../components/EmptyState.jsx";
import { getCareQueue, updateCareStatus } from "../services/api.js";

//care Management queue statuses

const STATUS_OPTIONS = ["Pending", "Outreach Scheduled", "In Progress", "Completed"];

export default function CareManagement() {
  const [queue, setQueue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await getCareQueue();
      setQueue(data.queue);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.error || "Could not load the care management queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleStatusChange = async (id, status) => {
    setQueue((q) => q.map((item) => (item.id === id ? { ...item, status } : item)));
    try {
      await updateCareStatus(id, status);
    } catch (err) {
      load();
    }
  };

  return (
    <>
      <TopBar title="Care Management" subtitle="Outreach queue prioritized by risk" />
      <div className="content">
        {loading ? (
          <LoadingRow />
        ) : error ? (
          <EmptyState title="Couldn't load the queue" description={error} />
        ) : queue.length === 0 ? (
          <EmptyState title="Queue is empty" description="Run a risk assessment - patients flagged medium or high risk will appear here." />
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Patient</th>
                    <th>Priority</th>
                    <th>Risk</th>
                    <th>Main Driver</th>
                    <th>Recommended Action</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <Link to={`/patients/${item.patientId}`} className="mono" style={{ color: "var(--brand-dark)", fontWeight: 600 }}>
                          {item.patientId.slice(0, 10)}&hellip;
                        </Link>
                      </td>
                      <td>
                        <RiskBadge level={item.priority} />
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: 6 }}>
                          <RiskBadge level={item.acuteRisk} />
                          <RiskBadge level={item.progressionRisk} />
                        </div>
                      </td>
                      <td className="text-muted">{item.mainDriver}</td>
                      <td className="text-muted">{item.recommendedAction}</td>
                      <td>
                        <select
                          className="select"
                          value={item.status}
                          onChange={(e) => handleStatusChange(item.id, e.target.value)}
                        >
                          {STATUS_OPTIONS.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
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
