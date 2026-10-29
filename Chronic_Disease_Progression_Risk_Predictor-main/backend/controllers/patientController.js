const Patient = require("../models/Patient");
const Condition = require("../models/Condition");
const Encounter = require("../models/Encounter");
const Medication = require("../models/Medication");
const Observation = require("../models/Observation");
const SDOH = require("../models/SDOH");
const Prediction = require("../models/Prediction");
const { ApiError } = require("../middleware/errorHandler");

const CHRONIC_KEYWORDS = [
  "diabetes mellitus type 2",
  "prediabetes",
  "essential hypertension",
  "heart failure",
  "chronic kidney disease",
  "end-stage renal disease",
  "chronic obstructive bronchitis",
  "pulmonary emphysema",
  "ischemic heart disease",
  "myocardial infarction",
  "coronary artery bypass",
  "asthma",
  "atrial fibrillation",
];

function ageFromBirthDate(birthDate) {
  if (!birthDate) return null;
  const diffMs = Date.now() - new Date(birthDate).getTime();
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24 * 365.25)));
}

async function listPatients(req, res) {
  const { risk, disease, gender, minAge, maxAge, page = 1, limit = 25, search } = req.query;
  const pageNum = Math.max(1, parseInt(page, 10) || 1);
  const limitNum = Math.min(200, Math.max(1, parseInt(limit, 10) || 25));

  const patientFilter = {};
  if (gender) patientFilter.gender = gender;
  if (search) patientFilter.patientId = { $regex: search, $options: "i" };

  let patientIdSubset = null;

  if (disease) {
    const rx = new RegExp(disease, "i");
    const matches = await Condition.find({ description: rx }).distinct("patientId");
    patientIdSubset = new Set(matches);
  }

  if (risk) {
    const riskUpper = risk.toUpperCase();
    const latestPerPatient = await Prediction.aggregate([
      { $sort: { patientId: 1, predictionDate: -1 } },
      {
        $group: {
          _id: "$patientId",
          acuteRisk: { $first: "$acuteRisk" },
          progressionRisk: { $first: "$progressionRisk" },
        },
      },
      {
        $match: {
          $or: [{ acuteRisk: riskUpper }, { progressionRisk: riskUpper }],
        },
      },
    ]);
    const riskIds = new Set(latestPerPatient.map((p) => p._id));
    patientIdSubset = patientIdSubset
      ? new Set([...patientIdSubset].filter((id) => riskIds.has(id)))
      : riskIds;
  }

  if (patientIdSubset) {
    patientFilter.patientId = { $in: [...patientIdSubset] };
  }

  const total = await Patient.countDocuments(patientFilter);
  let patients = await Patient.find(patientFilter)
    .sort({ patientId: 1 })
    .skip((pageNum - 1) * limitNum)
    .limit(limitNum)
    .lean();

  if (minAge || maxAge) {
    patients = patients.filter((p) => {
      const age = ageFromBirthDate(p.birthDate);
      if (age === null) return false;
      if (minAge && age < parseInt(minAge, 10)) return false;
      if (maxAge && age > parseInt(maxAge, 10)) return false;
      return true;
    });
  }

  const patientIds = patients.map((p) => p.patientId);

  const [conditions, latestPredictions, latestEncounters] = await Promise.all([
    Condition.find({ patientId: { $in: patientIds }, description: { $in: CHRONIC_KEYWORDS.map((k) => new RegExp(k, "i")) } }).lean(),
    Prediction.aggregate([
      { $match: { patientId: { $in: patientIds } } },
      { $sort: { predictionDate: -1 } },
      { $group: { _id: "$patientId", doc: { $first: "$$ROOT" } } },
    ]),
    Encounter.aggregate([
      { $match: { patientId: { $in: patientIds } } },
      { $sort: { start: -1 } },
      { $group: { _id: "$patientId", start: { $first: "$start" }, encounterClass: { $first: "$encounterClass" } } },
    ]),
  ]);

  const conditionsByPatient = {};
  for (const c of conditions) {
    if (!conditionsByPatient[c.patientId]) conditionsByPatient[c.patientId] = new Set();
    conditionsByPatient[c.patientId].add(c.description);
  }
  const predictionByPatient = Object.fromEntries(latestPredictions.map((p) => [p._id, p.doc]));
  const encounterByPatient = Object.fromEntries(latestEncounters.map((e) => [e._id, e]));

  const results = patients.map((p) => ({
    patientId: p.patientId,
    age: ageFromBirthDate(p.birthDate),
    gender: p.gender,
    chronicConditions: [...(conditionsByPatient[p.patientId] || [])],
    acuteRisk: predictionByPatient[p.patientId]?.acuteRisk || null,
    acuteProbability: predictionByPatient[p.patientId]?.acuteProbability ?? null,
    progressionRisk: predictionByPatient[p.patientId]?.progressionRisk || null,
    progressionProbability: predictionByPatient[p.patientId]?.progressionProbability ?? null,
    lastEncounter: encounterByPatient[p.patientId]?.start || null,
    lastPredictionDate: predictionByPatient[p.patientId]?.predictionDate || null,
  }));

  res.json({
    patients: results,
    pagination: { page: pageNum, limit: limitNum, total, pages: Math.ceil(total / limitNum) },
  });
}

async function getPatient(req, res) {
  const { patientId } = req.params;
  const patient = await Patient.findOne({ patientId }).lean();
  if (!patient) throw new ApiError(404, "Patient not found");

  const [conditions, latestPrediction, predictionHistory] = await Promise.all([
    Condition.find({ patientId }).sort({ start: 1 }).lean(),
    Prediction.findOne({ patientId }).sort({ predictionDate: -1 }).lean(),
    Prediction.find({ patientId }).sort({ predictionDate: -1 }).limit(5).lean(),
  ]);

  res.json({
    patient: { ...patient, age: ageFromBirthDate(patient.birthDate) },
    chronicConditions: conditions
      .filter((c) => CHRONIC_KEYWORDS.some((k) => c.description.toLowerCase().includes(k)))
      .map((c) => c.description)
      .filter((v, i, arr) => arr.indexOf(v) === i),
    latestPrediction,
    predictionHistory,
  });
}

async function getPatientTimeline(req, res) {
  const { patientId } = req.params;
  const patient = await Patient.findOne({ patientId }).lean();
  if (!patient) throw new ApiError(404, "Patient not found");

  const [conditions, encounters, medications, observations, sdoh] = await Promise.all([
    Condition.find({ patientId }).lean(),
    Encounter.find({ patientId }).lean(),
    Medication.find({ patientId }).lean(),
    Observation.find({ patientId }).lean(),
    SDOH.find({ patientId }).lean(),
  ]);

  const events = [];
  for (const c of conditions) {
    events.push({ type: "diagnosis", date: c.start, title: c.description, meta: { stop: c.stop } });
  }
  for (const e of encounters) {
    events.push({
      type: e.encounterClass === "emergency" ? "ed_visit" : "encounter",
      date: e.start,
      title: e.description || e.encounterClass,
      meta: { encounterClass: e.encounterClass, stop: e.stop },
    });
  }
  for (const m of medications) {
    events.push({ type: "medication", date: m.start, title: m.description, meta: { stop: m.stop } });
  }
  for (const o of observations) {
    events.push({
      type: o.category === "laboratory" ? "lab" : o.category === "vital-signs" ? "vital" : "observation",
      date: o.date,
      title: o.description,
      meta: { value: o.value, units: o.units, category: o.category },
    });
  }
  for (const s of sdoh) {
    events.push({ type: "sdoh", date: s.recordedDate || s.createdAt, title: s.type, meta: { value: s.value } });
  }

  events.sort((a, b) => new Date(b.date) - new Date(a.date));
  const capped = events.slice(0, 100); // keep the timeline light - most recent 100 events

  res.json({ patientId, events: capped, totalEvents: events.length });
}

module.exports = { listPatients, getPatient, getPatientTimeline };
