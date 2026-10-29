const express = require("express");
const { listPatients, getPatient, getPatientTimeline } = require("../controllers/patientController");

const router = express.Router();

router.get("/", listPatients);
router.get("/:patientId", getPatient);
router.get("/:patientId/timeline", getPatientTimeline);

module.exports = router;
