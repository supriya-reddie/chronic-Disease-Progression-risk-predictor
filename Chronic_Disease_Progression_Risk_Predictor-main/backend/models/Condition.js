const mongoose = require("mongoose");

const ConditionSchema = new mongoose.Schema(
  {
    patientId: { type: String, required: true, index: true },
    start: { type: Date, required: true },
    stop: { type: Date, default: null },
    code: { type: String, default: null },
    description: { type: String, required: true },
  },
  { timestamps: true }
);

ConditionSchema.index({ patientId: 1, start: 1 });

module.exports = mongoose.model("Condition", ConditionSchema);
