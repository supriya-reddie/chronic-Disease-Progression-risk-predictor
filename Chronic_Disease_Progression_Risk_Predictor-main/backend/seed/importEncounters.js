const Encounter = require("../models/Encounter");
const { readCsvUpper, toDate } = require("./csvUtils");

async function importEncounters(filePath) {
  const rows = await readCsvUpper(filePath);
  await Encounter.deleteMany({});
  const docs = rows
    .map((r) => ({
      patientId: String(r.PATIENT || "").trim(),
      start: toDate(r.START),
      stop: toDate(r.STOP),
      encounterClass: (r.ENCOUNTERCLASS || "").toLowerCase().trim(),
      description: (r.DESCRIPTION || "").trim(),
      reasonDescription: r.REASONDESCRIPTION || null,
    }))
    .filter((d) => d.patientId && d.start);

  if (docs.length === 0) return { total: rows.length, inserted: 0 };
  const CHUNK = 5000;
  let inserted = 0;
  for (let i = 0; i < docs.length; i += CHUNK) {
    const res = await Encounter.insertMany(docs.slice(i, i + CHUNK), { ordered: false });
    inserted += res.length;
  }
  return { total: rows.length, inserted };
}

module.exports = { importEncounters };
