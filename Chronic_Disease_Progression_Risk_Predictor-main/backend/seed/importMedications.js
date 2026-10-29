const Medication = require("../models/Medication");
const { readCsvUpper, toDate, toNumber } = require("./csvUtils");

async function importMedications(filePath) {
  const rows = await readCsvUpper(filePath);
  await Medication.deleteMany({});
  const docs = rows
    .map((r) => ({
      patientId: String(r.PATIENT || "").trim(),
      start: toDate(r.START),
      stop: toDate(r.STOP),
      description: (r.DESCRIPTION || "").trim(),
      dispenses: toNumber(r.DISPENSES),
    }))
    .filter((d) => d.patientId && d.start && d.description);

  if (docs.length === 0) return { total: rows.length, inserted: 0 };
  const CHUNK = 5000;
  let inserted = 0;
  for (let i = 0; i < docs.length; i += CHUNK) {
    const res = await Medication.insertMany(docs.slice(i, i + CHUNK), { ordered: false });
    inserted += res.length;
  }
  return { total: rows.length, inserted };
}

module.exports = { importMedications };
