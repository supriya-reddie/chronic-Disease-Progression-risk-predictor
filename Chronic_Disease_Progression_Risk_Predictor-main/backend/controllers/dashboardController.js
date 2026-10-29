const Patient = require("../models/Patient");
const Condition = require("../models/Condition");
const Prediction = require("../models/Prediction");
const Encounter = require("../models/Encounter");

const CHRONIC_LABELS = {
  "diabetes mellitus type 2": "Diabetes (Type 2)",
  "prediabetes": "Prediabetes",
  "essential hypertension": "Hypertension",
  "heart failure": "Heart Failure",
  "chronic kidney disease": "Chronic Kidney Disease",
  "end-stage renal disease": "End-Stage Renal Disease",
  "chronic obstructive bronchitis": "COPD",
  "pulmonary emphysema": "Emphysema",
  "ischemic heart disease": "Ischemic Heart Disease",
  "myocardial infarction": "Prior Myocardial Infarction",
  "coronary artery bypass": "Coronary Artery Bypass",
  "asthma": "Asthma",
  "atrial fibrillation": "Atrial Fibrillation",
};

async function latestPredictionsMap() {
  const latest = await Prediction.aggregate([
    { $sort: { patientId: 1, predictionDate: -1 } },
    { $group: { _id: "$patientId", doc: { $first: "$$ROOT" } } },
  ]);
  return latest.map((l) => l.doc);
}

async function getSummary(req, res) {
  const totalPatients = await Patient.countDocuments();
  const latestPreds = await latestPredictionsMap();

  const highAcute = latestPreds.filter((p) => p.acuteRisk === "HIGH").length;
  const mediumAcute = latestPreds.filter((p) => p.acuteRisk === "MEDIUM").length;
  const lowAcute = latestPreds.filter((p) => p.acuteRisk === "LOW").length;

  const highProgression = latestPreds.filter((p) => p.progressionRisk === "HIGH").length;
  const mediumProgression = latestPreds.filter((p) => p.progressionRisk === "MEDIUM").length;
  const lowProgression = latestPreds.filter((p) => p.progressionRisk === "LOW").length;

  const requiringFollowUp = latestPreds.filter(
    (p) => p.acuteRisk === "HIGH" || p.progressionRisk === "HIGH" || p.acuteRisk === "MEDIUM" || p.progressionRisk === "MEDIUM"
  ).length;

  const diseaseCounts = {};
  const conditionAgg = await Condition.aggregate([
    { $group: { _id: { $toLower: "$description" }, count: { $sum: 1 }, patients: { $addToSet: "$patientId" } } },
  ]);
  for (const [keyword, label] of Object.entries(CHRONIC_LABELS)) {
    const matches = conditionAgg.filter((c) => c._id.includes(keyword));
    const patientSet = new Set();
    matches.forEach((m) => m.patients.forEach((p) => patientSet.add(p)));
    if (patientSet.size > 0) diseaseCounts[label] = patientSet.size;
  }

  const recentHighRisk = latestPreds
    .filter((p) => p.acuteRisk === "HIGH" || p.progressionRisk === "HIGH")
    .sort((a, b) => new Date(b.predictionDate) - new Date(a.predictionDate))
    .slice(0, 8)
    .map((p) => ({
      patientId: p.patientId,
      acuteRisk: p.acuteRisk,
      acuteProbability: p.acuteProbability,
      progressionRisk: p.progressionRisk,
      progressionProbability: p.progressionProbability,
      predictionDate: p.predictionDate,
    }));

  const lastRun = latestPreds.length
    ? latestPreds.reduce((max, p) => (new Date(p.predictionDate) > new Date(max) ? p.predictionDate : max), latestPreds[0].predictionDate)
    : null;

  res.json({
    totalPatients,
    patientsScored: latestPreds.length,
    highAcuteRisk: highAcute,
    mediumAcuteRisk: mediumAcute,
    lowAcuteRisk: lowAcute,
    highProgressionRisk: highProgression,
    mediumProgressionRisk: mediumProgression,
    lowProgressionRisk: lowProgression,
    requiringFollowUp,
    acuteRiskDistribution: [
      { name: "Low", value: lowAcute },
      { name: "Medium", value: mediumAcute },
      { name: "High", value: highAcute },
    ],
    progressionRiskDistribution: [
      { name: "Low", value: lowProgression },
      { name: "Medium", value: mediumProgression },
      { name: "High", value: highProgression },
    ],
    chronicDiseaseDistribution: Object.entries(diseaseCounts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value),
    recentHighRiskPatients: recentHighRisk,
    lastAssessmentRun: lastRun,
  });
}

async function getHighRiskPatients(req, res) {
  const latestPreds = await latestPredictionsMap();
  const highRisk = latestPreds
    .filter((p) => p.acuteRisk === "HIGH" || p.progressionRisk === "HIGH")
    .sort((a, b) => Math.max(b.acuteProbability, b.progressionProbability) - Math.max(a.acuteProbability, a.progressionProbability));

  const patientIds = highRisk.map((p) => p.patientId);
  const [patients, lastEncounters] = await Promise.all([
    Patient.find({ patientId: { $in: patientIds } }).lean(),
    Encounter.aggregate([
      { $match: { patientId: { $in: patientIds } } },
      { $sort: { start: -1 } },
      { $group: { _id: "$patientId", start: { $first: "$start" } } },
    ]),
  ]);
  const patientById = Object.fromEntries(patients.map((p) => [p.patientId, p]));
  const encById = Object.fromEntries(lastEncounters.map((e) => [e._id, e.start]));

  const results = highRisk.map((p) => {
    const acuteTop = p.acuteTopFactors?.[0]?.label || p.acuteTopFactors?.[0]?.feature;
    const progTop = p.progressionTopFactors?.[0]?.label || p.progressionTopFactors?.[0]?.feature;
    const mainDriver =
      p.acuteRisk === "HIGH" && acuteTop
        ? acuteTop
        : p.progressionRisk === "HIGH" && progTop
        ? progTop
        : acuteTop || progTop || "Not available";
    return {
      patientId: p.patientId,
      gender: patientById[p.patientId]?.gender || null,
      acuteRisk: p.acuteRisk,
      acuteProbability: p.acuteProbability,
      progressionRisk: p.progressionRisk,
      progressionProbability: p.progressionProbability,
      mainDriver,
      lastEncounter: encById[p.patientId] || null,
      recommendations: p.recommendations,
    };
  });

  res.json({ patients: results, count: results.length });
}

module.exports = { getSummary, getHighRiskPatients };
