const SDOH = require("../models/SDOH");
const { readCsvUpper, toDate } = require("./csvUtils");
const fs = require("fs");

// Optional. Only runs if an sdoh CSV is present in the data directory.
// Expected columns: PATIENT, TYPE, VALUE, DATE
async function importSDOH(filePath) {
  if (!fs.existsSync(filePath)) {
    return { total: 0, inserted: 0, skipped: true };
  }
  const rows = await readCsvUpper(filePath);
  await SDOH.deleteMany({});
  const docs = rows
    .map((r) => ({
      patientId: String(r.PATIENT || "").trim(),
      type: (r.TYPE || "").trim(),
      value: r.VALUE || null,
      recordedDate: toDate(r.DATE),
    }))
    .filter((d) => d.patientId && d.type);

  if (docs.length === 0) return { total: rows.length, inserted: 0 };
  const res = await SDOH.insertMany(docs, { ordered: false });
  return { total: rows.length, inserted: res.length };
}

module.exports = { importSDOH };
