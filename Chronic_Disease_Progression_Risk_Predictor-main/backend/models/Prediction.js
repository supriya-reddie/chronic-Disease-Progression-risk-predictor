const mongoose = require("mongoose");

const TopFactorSchema = new mongoose.Schema(
  {
    feature: { type: String, default: null },
    value: { type: mongoose.Schema.Types.Mixed, default: null },
    contribution: { type: Number, default: null },
    direction: { type: String, enum: ["increases_risk", "decreases_risk", null], default: null },
    label: { type: String, default: null },
  },
  { _id: false }
);

const PredictionSchema = new mongoose.Schema(
  {
    patientId: { type: String, required: true, index: true },
    jobId: { type: String, index: true, default: null },
    predictionDate: { type: Date, required: true, default: Date.now },

    acuteProbability: { type: Number, required: true },
    acuteRisk: { type: String, enum: ["LOW", "MEDIUM", "HIGH"], required: true },

    progressionProbability: { type: Number, required: true },
    progressionRisk: { type: String, enum: ["LOW", "MEDIUM", "HIGH"], required: true },

    // Full engineered feature vector used for this prediction (from the ML service)
    features: { type: mongoose.Schema.Types.Mixed, default: {} },

    acuteExplanation: { type: String, default: "" },
    acuteTopFactors: { type: [TopFactorSchema], default: [] },

    progressionExplanation: { type: String, default: "" },
    progressionTopFactors: { type: [TopFactorSchema], default: [] },

    recommendations: { type: [String], default: [] },

    dataCompletenessScore: { type: Number, default: null },
    dataCompletenessCategory: { type: String, default: null },

    modelVersion: { type: String, default: "chronicare-v1" },

    // Care-management workflow status for the queue (page 27). Editable by
    // care managers in the UI; does not affect model output.
    careStatus: {
      type: String,
      enum: ["Pending", "Outreach Scheduled", "In Progress", "Completed"],
      default: "Pending",
    },
  },
  { timestamps: true }
);

PredictionSchema.index({ patientId: 1, predictionDate: -1 });
PredictionSchema.index({ acuteRisk: 1 });
PredictionSchema.index({ progressionRisk: 1 });

module.exports = mongoose.model("Prediction", PredictionSchema);
