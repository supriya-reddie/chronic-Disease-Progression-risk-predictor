require("dotenv").config();
require("express-async-errors");

const express = require("express");
const cors = require("cors");
const morgan = require("morgan");

const { connectDB } = require("./config/db");
const { notFound, errorHandler } = require("./middleware/errorHandler");

const healthRoutes = require("./routes/health");
const patientRoutes = require("./routes/patients");
const predictionRoutes = require("./routes/predictions");
const dashboardRoutes = require("./routes/dashboard");
const highRiskRoutes = require("./routes/highRiskPatients");
const careManagementRoutes = require("./routes/careManagement");

const app = express();

app.use(cors({ origin: process.env.CORS_ORIGIN || "*" }));
app.use(express.json({ limit: "2mb" }));
app.use(morgan(process.env.NODE_ENV === "production" ? "combined" : "dev"));

app.use("/api/health", healthRoutes);
app.use("/api/patients", patientRoutes);
app.use("/api/predictions", predictionRoutes);
app.use("/api/dashboard", dashboardRoutes);
app.use("/api/high-risk-patients", highRiskRoutes);
app.use("/api/care-management", careManagementRoutes);

app.use(notFound);
app.use(errorHandler);

const PORT = process.env.PORT || 5000;

async function start() {
  try {
    await connectDB();
  } catch (err) {
    console.error("[FATAL] Could not connect to MongoDB:", err.message);
    console.error("Set MONGO_URI in backend/.env and make sure MongoDB is running.");
    process.exit(1);
  }

  app.listen(PORT, () => {
    console.log("=".repeat(60));
    console.log("Chronic Disease Risk Intelligence Platform - API");
    console.log("Listening on port " + PORT);
    console.log("ML service: " + (process.env.ML_SERVICE_URL || "http://localhost:8000"));
    console.log("=".repeat(60));
  });
}

start();

module.exports = app;
