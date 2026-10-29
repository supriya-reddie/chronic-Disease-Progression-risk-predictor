const { v4: uuidv4 } = require("uuid");
const Patient = require("../models/Patient");
const Prediction = require("../models/Prediction");
const PredictionJob = require("../models/PredictionJob");
const mlServiceClient = require("../services/mlServiceClient");
const { ApiError } = require("../middleware/errorHandler");

async function runBatch(req, res) {
  const runningJob = await PredictionJob.findOne({ status: { $in: ["pending", "running"] } });
  if (runningJob) {
    return res.status(409).json({
      error: "A batch prediction job is already running.",
      jobId: runningJob.jobId,
      status: runningJob.status,
    });
  }

  const totalPatients = await Patient.countDocuments();
  if (totalPatients === 0) {
    throw new ApiError(400, "No patients found in the database. Import patient CSV data first.");
  }

  const jobId = "JOB-" + uuidv4().slice(0, 8).toUpperCase();
  await PredictionJob.create({
    jobId,
    status: "pending",
    total: totalPatients,
    processed: 0,
    successful: 0,
    failed: 0,
    startedAt: new Date(),
  });

  try {
    await mlServiceClient.triggerBatchPrediction(jobId);
  } catch (err) {
    await PredictionJob.updateOne(
      { jobId },
      { status: "failed", errorMessage: "Could not reach ML service: " + err.message, completedAt: new Date() }
    );
    throw new ApiError(503, "Could not start the ML service batch job.", err.message);
  }

  res.status(202).json({ jobId, status: "started", totalPatients });
}

async function getJobStatus(req, res) {
  const job = await PredictionJob.findOne({ jobId: req.params.jobId }).lean();
  if (!job) throw new ApiError(404, "Prediction job not found");
  res.json(job);
}

async function listJobs(req, res) {
  const jobs = await PredictionJob.find().sort({ createdAt: -1 }).limit(50).lean();
  res.json({ jobs });
}

async function getPatientPrediction(req, res) {
  const prediction = await Prediction.findOne({ patientId: req.params.patientId }).sort({ predictionDate: -1 }).lean();
  if (!prediction) throw new ApiError(404, "No prediction found for this patient. Run a risk assessment first.");
  res.json(prediction);
}

async function runSinglePatient(req, res) {
  const { patientId } = req.params;
  const patient = await Patient.findOne({ patientId });
  if (!patient) throw new ApiError(404, "Patient not found");

  try {
    const result = await mlServiceClient.triggerSinglePrediction(patientId);
    res.json(result);
  } catch (err) {
    throw new ApiError(503, "Could not reach the ML service to score this patient.", err.message);
  }
}

module.exports = { runBatch, getJobStatus, listJobs, getPatientPrediction, runSinglePatient };
