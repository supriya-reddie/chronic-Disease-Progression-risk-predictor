const axios = require("axios");

const ML_SERVICE_URL = process.env.ML_SERVICE_URL || "http://localhost:8000";

const client = axios.create({
  baseURL: ML_SERVICE_URL,
  timeout: 60000, // scoring involves real model inference; give it room
});

/**
 * Kicks off batch prediction on the Python ML service for a given jobId.
 * The ML service runs this as a background task: it fetches raw patient
 * data from MongoDB itself, engineers features, runs the frozen PKL models,
 * and writes Prediction documents + job progress back to MongoDB.
 * This call is intentionally fire-and-forget from Node's perspective -
 * Node never touches feature engineering or model inference.
 */
async function triggerBatchPrediction(jobId, patientIds = null) {
  const res = await client.post("/predict/batch", {
    job_id: jobId,
    patient_ids: patientIds, // null = all patients
  });
  return res.data;
}

async function triggerSinglePrediction(patientId) {
  const res = await client.post("/predict/patient", { patient_id: patientId });
  return res.data;
}

async function checkMlServiceHealth() {
  try {
    const res = await client.get("/health", { timeout: 4000 });
    return { reachable: true, ...res.data };
  } catch (err) {
    return { reachable: false, error: err.message };
  }
}

module.exports = {
  triggerBatchPrediction,
  triggerSinglePrediction,
  checkMlServiceHealth,
};
