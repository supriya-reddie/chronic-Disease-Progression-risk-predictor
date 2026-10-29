const mongoose = require("mongoose");

const ObservationSchema = new mongoose.Schema(
  {
    patientId: { type: String, required: true, index: true },
    date: { type: Date, required: true },
    category: { type: String, default: "unknown" }, // laboratory, vital-signs, ...
    description: { type: String, required: true },
    value: { type: String, default: null },
    valueNumeric: { type: Number, default: null },
    units: { type: String, default: null },
  },
  { timestamps: true }
);

ObservationSchema.index({ patientId: 1, date: 1 });
ObservationSchema.index({ patientId: 1, category: 1 });

module.exports = mongoose.model("Observation", ObservationSchema);
