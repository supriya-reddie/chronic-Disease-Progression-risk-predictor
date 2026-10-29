const express = require("express");
const mongoose = require("mongoose");
const mlServiceClient = require("../services/mlServiceClient");

const router = express.Router();

router.get("/", async (req, res) => {
  const mongoState = mongoose.connection.readyState; // 1 = connected
  const mlHealth = await mlServiceClient.checkMlServiceHealth();

  const healthy = mongoState === 1 && mlHealth.reachable;

  res.status(healthy ? 200 : 503).json({
    status: healthy ? "ok" : "degraded",
    mongo: mongoState === 1 ? "connected" : "unavailable",
    mlService: mlHealth.reachable ? "reachable" : "unreachable",
    mlServiceDetail: mlHealth,
    timestamp: new Date().toISOString(),
  });
});

module.exports = router;
