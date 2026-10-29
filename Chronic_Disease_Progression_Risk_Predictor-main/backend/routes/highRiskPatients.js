const express = require("express");
const { getHighRiskPatients } = require("../controllers/dashboardController");

const router = express.Router();

router.get("/", getHighRiskPatients);

module.exports = router;
