import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
});

// --- Dashboard --------------------------------------------------------
export const getDashboardSummary = () => api.get("/dashboard/summary").then((r) => r.data);

// --- Patients -----------------------------------------------------------
export const getPatients = (params) => api.get("/patients", { params }).then((r) => r.data);
export const getPatient = (patientId) => api.get(`/patients/${patientId}`).then((r) => r.data);
export const getPatientTimeline = (patientId) => api.get(`/patients/${patientId}/timeline`).then((r) => r.data);

// --- Predictions -----------------------------------------------------------
export const runBatchPrediction = () => api.post("/predictions/run-batch").then((r) => r.data);
export const getJobStatus = (jobId) => api.get(`/predictions/job/${jobId}`).then((r) => r.data);
export const listJobs = () => api.get("/predictions/jobs").then((r) => r.data);
export const getPatientPrediction = (patientId) => api.get(`/predictions/${patientId}`).then((r) => r.data);
export const runSinglePatientPrediction = (patientId) =>
  api.post(`/predictions/patient/${patientId}/run`).then((r) => r.data);

// --- High risk -----------------------------------------------------------
export const getHighRiskPatients = () => api.get("/high-risk-patients").then((r) => r.data);

// --- Care management -------------------------------------------------------
export const getCareQueue = () => api.get("/care-management").then((r) => r.data);
export const updateCareStatus = (predictionId, status) =>
  api.patch(`/care-management/${predictionId}/status`, { status }).then((r) => r.data);

// --- Health -----------------------------------------------------------------
export const getHealth = () => api.get("/health").then((r) => r.data);
