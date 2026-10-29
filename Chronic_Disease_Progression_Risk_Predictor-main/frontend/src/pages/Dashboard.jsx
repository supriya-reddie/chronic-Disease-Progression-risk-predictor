import { useCallback, useEffect, useRef, useState } from "react";
import TopBar from "../components/TopBar.jsx";
import StatCard from "../components/StatCard.jsx";
import LoadingRow from "../components/LoadingRow.jsx";
import EmptyState from "../components/EmptyState.jsx";
import RiskDistributionChart from "../charts/RiskDistributionChart.jsx";
import { getDashboardSummary, getJobStatus, runBatchPrediction } from "../services/api.js";

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [job, setJob] = useState(null);
  const [jobError, setJobError] = useState(null);
  const pollRef = useRef(null);

  const loadSummary = useCallback(async () => {
    try {
      const data = await getDashboardSummary();
      setSummary(data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.error || "Could not load dashboard data. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    return () => clearInterval(pollRef.current);
  }, []);

  const pollJob = useCallback(
    (jobId) => {
      pollRef.current = setInterval(async () => {
        try {
          const data = await getJobStatus(jobId);
          setJob(data);
          if (data.status === "completed" || data.status === "failed") {
            clearInterval(pollRef.current);
            if (data.status === "completed") loadSummary();
          }
        } catch (err) {
          clearInterval(pollRef.current);
          setJobError("Lost connection while checking job status.");
        }
      }, 1500);
    },
    [loadSummary]
  );

  const handleRunBatch = async () => {
    setJobError(null);
    try {
      const res = await runBatchPrediction();
      setJob({ jobId: res.jobId, status: "running", total: res.totalPatients, processed: 0 });
      pollJob(res.jobId);
    } catch (err) {
      if (err.response?.status === 409) {
        setJob({ jobId: err.response.data.jobId, status: err.response.data.status, total: 0, processed: 0 });
        pollJob(err.response.data.jobId);
      } else {
        setJobError(err.response?.data?.error || "Could not start the risk assessment.");
      }
    }
  };

  const isRunning = job && (job.status === "pending" || job.status === "running");
  const pct = job && job.total > 0 ? Math.min(100, Math.round((job.processed / job.total) * 100)) : 0;

  if (loading) {
    return (
      <>
        <TopBar title="Dashboard" subtitle="Chronic Disease Risk Intelligence Platform" />
        <div className="content">
          <LoadingRow label="Loading dashboard…" />
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <TopBar title="Dashboard" subtitle="Chronic Disease Risk Intelligence Platform" />
        <div className="content">
          <EmptyState title="Couldn't load the dashboard" description={error} />
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar title="Dashboard" subtitle="Population risk overview">
        <button className="btn btn-primary" onClick={handleRunBatch} disabled={isRunning}>
          {isRunning ? "Assessment running…" : "Run Risk Assessment"}
        </button>
      </TopBar>

      <div className="content">
        {isRunning && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-title">Processing patients</div>
            <div className="card-sub">
              {job.processed?.toLocaleString() || 0} of {job.total?.toLocaleString() || 0} patients scored
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${pct}%` }} />
            </div>
            <div style={{ marginTop: 10, fontSize: 14 }} className="text-muted">
              {pct}% complete
            </div>
          </div>
        )}
        {job?.status === "completed" && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-title">Risk assessment completed</div>
            <div className="text-muted">
              Scored {job.successful?.toLocaleString() || job.total?.toLocaleString()} of {job.total?.toLocaleString()}{" "}
              patients{job.failed ? ` (${job.failed} failed)` : ""}.
            </div>
          </div>
        )}
        {job?.status === "failed" && (
          <div className="card" style={{ marginBottom: 20 }}>
            <EmptyState title="Batch run failed" description={job.errorMessage || "The ML service reported an error."} />
          </div>
        )}
        {jobError && (
          <div className="card" style={{ marginBottom: 20, borderColor: "var(--risk-high)" }}>
            <span style={{ color: "var(--risk-high)" }}>{jobError}</span>
          </div>
        )}

        <div className="grid grid-4" style={{ marginBottom: 20 }}>
          <StatCard label="Total Patients" value={summary.totalPatients?.toLocaleString() ?? 0} note={`${summary.patientsScored?.toLocaleString() ?? 0} scored`} />
          <StatCard label="High Acute Risk" value={summary.highAcuteRisk?.toLocaleString() ?? 0} note="May need urgent care soon" />
          <StatCard label="High Progression Risk" value={summary.highProgressionRisk?.toLocaleString() ?? 0} note="Chronic disease worsening" />
          <StatCard label="Requiring Follow-up" value={summary.requiringFollowUp?.toLocaleString() ?? 0} note="Medium or high risk" />
        </div>

        <div className="grid grid-2">
          <div className="card">
            <div className="card-title">Acute Risk</div>
            <div className="card-sub">Chance of needing urgent/emergency care in the next 90 days</div>
            <RiskDistributionChart data={summary.acuteRiskDistribution || []} />
          </div>
          <div className="card">
            <div className="card-title">Progression Risk</div>
            <div className="card-sub">Chance of a chronic condition getting worse</div>
            <RiskDistributionChart data={summary.progressionRiskDistribution || []} />
          </div>
        </div>
      </div>
    </>
  );
}
