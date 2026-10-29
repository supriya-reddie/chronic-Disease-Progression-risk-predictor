import { useEffect, useState } from "react";
import TopBar from "../components/TopBar.jsx";
import LoadingRow from "../components/LoadingRow.jsx";
import EmptyState from "../components/EmptyState.jsx";
import { listJobs } from "../services/api.js";

const STATUS_COLOR = {
  completed: "LOW",
  running: "MEDIUM",
  pending: "MEDIUM",
  failed: "HIGH",
};

function formatDateTime(value) {
  if (!value) return "\u2014";
  return new Date(value).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function PredictionHistory() {
  const [jobs, setJobs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await listJobs();
        setJobs(data.jobs);
        setError(null);
      } catch (err) {
        setError(err.response?.data?.error || "Could not load prediction history.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <>
      <TopBar title="Prediction History" subtitle="Batch risk-assessment runs" />
      <div className="content">
        {loading ? (
          <LoadingRow />
        ) : error ? (
          <EmptyState title="Couldn't load prediction history" description={error} />
        ) : jobs.length === 0 ? (
          <EmptyState title="No assessment runs yet" description="Run a risk assessment from the Dashboard to see history here." />
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Started</th>
                    <th>Completed</th>
                    <th>Status</th>
                    <th>Total</th>
                    <th>Successful</th>
                    <th>Failed</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.jobId}>
                      <td className="mono">{job.jobId}</td>
                      <td className="text-muted">{formatDateTime(job.startedAt)}</td>
                      <td className="text-muted">{formatDateTime(job.completedAt)}</td>
                      <td>
                        <span className={`risk-badge ${STATUS_COLOR[job.status] || "NONE"}`}>
                          <span className="risk-badge-dot" />
                          {job.status}
                        </span>
                      </td>
                      <td>{job.total?.toLocaleString() ?? 0}</td>
                      <td>{job.successful?.toLocaleString() ?? 0}</td>
                      <td>{job.failed?.toLocaleString() ?? 0}</td>
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
