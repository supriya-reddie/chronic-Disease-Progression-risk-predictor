const mongoose = require("mongoose");

const MedicationSchema = new mongoose.Schema(
  {
    patientId: { type: String, required: true, index: true },
    start: { type: Date, required: true },
    stop: { type: Date, default: null },
    description: { type: String, required: true },
    dispenses: { type: Number, default: null },
  },
  { timestamps: true }
);

MedicationSchema.index({ patientId: 1, start: 1 });

module.exports = mongoose.model("Medication", MedicationSchema);
