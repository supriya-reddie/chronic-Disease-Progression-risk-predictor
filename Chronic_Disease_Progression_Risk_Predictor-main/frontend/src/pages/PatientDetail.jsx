import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import TopBar from "../components/TopBar.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import LoadingRow from "../components/LoadingRow.jsx";
import EmptyState from "../components/EmptyState.jsx";
import { getPatient, getPatientTimeline, runSinglePatientPrediction } from "../services/api.js";

const TYPE_LABELS = {
  diagnosis: "Diagnosis",
  encounter: "Visit",
  ed_visit: "ER Visit",
  medication: "Medication",
  lab: "Lab result",
  vital: "Vital sign",
  observation: "Observation",
  sdoh: "Social factor",
};

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function FactorList({ factors }) {
  if (!factors || factors.length === 0) {
    return <div className="text-faint">No clear driving factor identified.</div>;
  }
  return (
    <div>
      {factors.map((f, idx) => (
        <div className="factor-row" key={idx}>
          <div>
            <div style={{ fontWeight: 600 }}>{f.label || f.feature}</div>
            {f.value !== null && f.value !== undefined && (
              <div className="text-faint" style={{ fontSize: 13 }}>
                Value on record: {f.value}
              </div>
            )}
          </div>
          {f.direction && (
            <span className={`factor-direction ${f.direction}`}>
              {f.direction === "increases_risk" ? "Raises risk" : "Lowers risk"}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

export default function PatientDetail() {
  const { patientId } = useParams();
  const [data, setData] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [patientData, timelineData] = await Promise.all([getPatient(patientId), getPatientTimeline(patientId)]);
      setData(patientData);
      setTimeline(timelineData.events);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.error || "Could not load this patient.");
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRunPrediction = async () => {
    setRunning(true);
    setRunError(null);
    try {
      await runSinglePatientPrediction(patientId);
      await load();
    } catch (err) {
      setRunError(err.response?.data?.error || "Could not score this patient. The ML service may be busy — try again.");
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <>
        <TopBar title="Patient" subtitle="" />
        <div className="content">
          <LoadingRow />
        </div>
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <TopBar title="Patient" subtitle="" />
        <div className="content">
          <EmptyState title="Couldn't load patient" description={error} />
        </div>
      </>
    );
  }

  const { patient, latestPrediction, chronicConditions } = data;

  return (
    <>
      <TopBar title={`Patient ${patient.patientId.slice(0, 10)}…`} subtitle={`${patient.age ?? "—"} years old · ${patient.gender || "—"}`}>
        <button className="btn btn-primary" onClick={handleRunPrediction} disabled={running}>
          {running ? "Scoring… (may take a moment)" : "Re-score Patient"}
        </button>
      </TopBar>

      <div className="content">
        {runError && (
          <div className="card" style={{ marginBottom: 20, borderColor: "var(--risk-high)" }}>
            <span style={{ color: "var(--risk-high)" }}>{runError}</span>
          </div>
        )}

        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title">Patient</div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", fontSize: 15, marginTop: 4 }}>
            <div>
              <span className="text-muted">Chronic conditions: </span>
              {chronicConditions?.length ? (
                chronicConditions.map((c, idx) => (
                  <span className="chip" key={idx}>
                    {c}
                  </span>
                ))
              ) : (
                <span className="text-faint">None recorded</span>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-2" style={{ marginBottom: 20 }}>
          <div className="card">
            <div className="card-title">Acute Event Risk</div>
            <div className="card-sub">Chance of needing urgent/emergency care in the next 90 days</div>
            {latestPrediction ? (
              <>
                <RiskBadge level={latestPrediction.acuteRisk} probability={latestPrediction.acuteProbability} />
                <p style={{ marginTop: 16, fontSize: 15 }}>{latestPrediction.acuteExplanation}</p>
                <div className="card-sub" style={{ marginTop: 18, marginBottom: 4 }}>
                  Top contributing factors
                </div>
                <FactorList factors={latestPrediction.acuteTopFactors} />
              </>
            ) : (
              <EmptyState title="Not yet scored" description="Run a risk assessment to see this patient's acute risk." />
            )}
          </div>

          <div className="card">
            <div className="card-title">Progression Risk</div>
            <div className="card-sub">Chance of a chronic condition getting worse</div>
            {latestPrediction ? (
              <>
                <RiskBadge level={latestPrediction.progressionRisk} probability={latestPrediction.progressionProbability} />
                <p style={{ marginTop: 16, fontSize: 15 }}>{latestPrediction.progressionExplanation}</p>
                <div className="card-sub" style={{ marginTop: 18, marginBottom: 4 }}>
                  Top contributing factors
                </div>
                <FactorList factors={latestPrediction.progressionTopFactors} />
              </>
            ) : (
              <EmptyState title="Not yet scored" description="Run a risk assessment to see this patient's progression risk." />
            )}
          </div>
        </div>

        {latestPrediction && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-title">Recommended Care Management</div>
            {latestPrediction.recommendations?.map((r, idx) => (
              <span className="chip" key={idx}>
                {r}
              </span>
            ))}
          </div>
        )}

        <div className="card">
          <div className="card-title">Recent Clinical History</div>
          <div className="card-sub">Most recent diagnoses, visits, medications, labs, and vitals</div>
          {timeline?.length ? (
            <div className="timeline" style={{ marginTop: 16, maxHeight: 480, overflowY: "auto" }}>
              {timeline.map((ev, idx) => (
                <div className="timeline-item" key={idx}>
                  <div className="timeline-date">{formatDate(ev.date)}</div>
                  <div className="timeline-title">{ev.title}</div>
                  <div className="timeline-type">{TYPE_LABELS[ev.type] || ev.type}</div>
                  {ev.meta?.value && (
                    <div className="text-muted" style={{ fontSize: 13, marginTop: 3 }}>
                      Value: {ev.meta.value} {ev.meta.units || ""}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No clinical history" description="No timeline events found for this patient." />
          )}
        </div>
      </div>
    </>
  );
}
