/**
 * CSV Import Pipeline
 * ====================
 * Loads RAW patient data (patients, conditions, encounters, medications,
 * observations, optional sdoh) from CSV files into MongoDB.
 *
 * This is step 1 of the pipeline:
 *   RAW CSV -> MongoDB -> [ML service] feature engineering -> PKL -> predictions -> MongoDB
 *
 * Usage:
 *   node seed/runImport.js
 *   node seed/runImport.js --dir /absolute/path/to/csvs
 *
 * File naming: the importer looks for the first matching filename from a
 * list of common conventions (Synthea-style and generic). Point --dir at a
 * folder containing your five (or six, with sdoh) CSV files.
 */
require("dotenv").config();
const path = require("path");
const fs = require("fs");
const mongoose = require("mongoose");
const { connectDB } = require("../config/db");
const { importPatients } = require("./importPatients");
const { importConditions } = require("./importConditions");
const { importEncounters } = require("./importEncounters");
const { importMedications } = require("./importMedications");
const { importObservations } = require("./importObservations");
const { importSDOH } = require("./importSDOH");

const FILE_CANDIDATES = {
  patients: ["patients.csv", "web_patients_1500.csv", "patients_chronic.csv"],
  conditions: ["conditions.csv", "web_conditions_1500.csv", "conditions_chronic.csv"],
  encounters: ["encounters.csv", "web_encounters_1500.csv", "encounters_chronic.csv"],
  medications: ["medications.csv", "web_medications_1500.csv", "medications_chronic.csv"],
  observations: ["observations.csv", "web_observations_1500.csv", "observations_chronic.csv"],
  sdoh: ["sdoh.csv"],
};

function resolveFile(dir, candidates) {
  for (const name of candidates) {
    const p = path.join(dir, name);
    if (fs.existsSync(p)) return p;
  }
  return path.join(dir, candidates[0]); // fall through, importer will report missing
}

async function main() {
  const dirArgIdx = process.argv.indexOf("--dir");
  const dataDir = dirArgIdx !== -1 ? process.argv[dirArgIdx + 1] : process.env.CSV_DATA_DIR || "../data";
  const resolvedDir = path.resolve(__dirname, dataDir);

  console.log("=".repeat(60));
  console.log("CDPRP CSV IMPORT PIPELINE");
  console.log("=".repeat(60));
  console.log("Data directory: " + resolvedDir);

  if (!fs.existsSync(resolvedDir)) {
    console.error("[FATAL] Data directory does not exist: " + resolvedDir);
    process.exit(1);
  }

  await connectDB();

  try {
    console.log("\n[1/6] Importing patients...");
    const patientsFile = resolveFile(resolvedDir, FILE_CANDIDATES.patients);
    const patResult = await importPatients(patientsFile);
    console.log("  " + JSON.stringify(patResult));

    console.log("\n[2/6] Importing conditions...");
    const condResult = await importConditions(resolveFile(resolvedDir, FILE_CANDIDATES.conditions));
    console.log("  " + JSON.stringify(condResult));

    console.log("\n[3/6] Importing encounters...");
    const encResult = await importEncounters(resolveFile(resolvedDir, FILE_CANDIDATES.encounters));
    console.log("  " + JSON.stringify(encResult));

    console.log("\n[4/6] Importing medications...");
    const medResult = await importMedications(resolveFile(resolvedDir, FILE_CANDIDATES.medications));
    console.log("  " + JSON.stringify(medResult));

    console.log("\n[5/6] Importing observations...");
    const obsResult = await importObservations(resolveFile(resolvedDir, FILE_CANDIDATES.observations));
    console.log("  " + JSON.stringify(obsResult));

    console.log("\n[6/6] Importing SDOH (optional)...");
    const sdohResult = await importSDOH(resolveFile(resolvedDir, FILE_CANDIDATES.sdoh));
    console.log("  " + JSON.stringify(sdohResult));

    console.log("\n" + "=".repeat(60));
    console.log("IMPORT COMPLETE");
    console.log("=".repeat(60));
    console.log("Next step: start the ML service, then POST /api/predictions/run-batch");
  } catch (err) {
    console.error("\n[FATAL] Import failed: " + err.message);
    process.exitCode = 1;
  } finally {
    await mongoose.disconnect();
  }
}

main();
