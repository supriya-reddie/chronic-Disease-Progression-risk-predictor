const express = require("express");
const { getQueue, updateStatus } = require("../controllers/careManagementController");

const router = express.Router();

router.get("/", getQueue);
router.patch("/:predictionId/status", updateStatus);

module.exports = router;
