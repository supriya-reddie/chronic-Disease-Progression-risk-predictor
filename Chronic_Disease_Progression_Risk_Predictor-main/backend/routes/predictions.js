const express = require("express");
const {
  runBatch,
  getJobStatus,
  listJobs,
  getPatientPrediction,
  runSinglePatient,
} = require("../controllers/predictionController");

const router = express.Router();

router.post("/run-batch", runBatch);
router.get("/jobs", listJobs);
router.get("/job/:jobId", getJobStatus);
router.post("/patient/:patientId/run", runSinglePatient);
router.get("/:patientId", getPatientPrediction);

module.exports = router;
