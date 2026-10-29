const mongoose = require("mongoose");

const PatientSchema = new mongoose.Schema(
  {
    patientId: { type: String, required: true, unique: true, index: true },
    birthDate: { type: Date },
    deathDate: { type: Date, default: null },
    gender: { type: String, enum: ["M", "F", "U"], default: "U" },
    marital: { type: String, default: null }, // 'M', 'S', etc.
    race: { type: String, default: null },
    ethnicity: { type: String, default: null },
    income: { type: Number, default: null },
    city: { type: String, default: null },
    state: { type: String, default: null },
    zip: { type: String, default: null },
    source: { type: String, default: "csv_import" },
  },
  { timestamps: true }
);

module.exports = mongoose.model("Patient", PatientSchema);
