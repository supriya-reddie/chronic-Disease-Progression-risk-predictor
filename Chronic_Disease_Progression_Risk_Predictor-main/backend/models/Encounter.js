const mongoose = require("mongoose");

const EncounterSchema = new mongoose.Schema(
  {
    patientId: { type: String, required: true, index: true },
    start: { type: Date, required: true },
    stop: { type: Date, default: null },
    encounterClass: { type: String, default: "" }, // ambulatory, emergency, inpatient, urgentcare, wellness...
    description: { type: String, default: "" },
    reasonDescription: { type: String, default: null },
  },
  { timestamps: true }
);

EncounterSchema.index({ patientId: 1, start: 1 });

module.exports = mongoose.model("Encounter", EncounterSchema);
