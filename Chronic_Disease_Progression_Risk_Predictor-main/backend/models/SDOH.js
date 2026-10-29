const mongoose = require("mongoose");

// Optional structured SDOH records (in addition to SDOH signals embedded in
// condition descriptions, which is what the trained model actually uses -
// see ml-service/feature_engineering.py). Used for display/context only.
const SDOHSchema = new mongoose.Schema(
  {
    patientId: { type: String, required: true, index: true },
    type: { type: String, required: true }, // e.g. transport_barrier, housing_insecurity
    value: { type: String, default: null },
    recordedDate: { type: Date, default: null },
  },
  { timestamps: true }
);

module.exports = mongoose.model("SDOH", SDOHSchema);
