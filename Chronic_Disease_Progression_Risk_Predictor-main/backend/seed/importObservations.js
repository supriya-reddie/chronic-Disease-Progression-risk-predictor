const Observation = require("../models/Observation");
const { readCsvUpper, toDate, toNumber } = require("./csvUtils");

async function importObservations(filePath) {
  const rows = await readCsvUpper(filePath);
  await Observation.deleteMany({});
  const docs = rows
    .map((r) => {
      const rawValue = r.VALUE_NUM !== undefined ? r.VALUE_NUM : r.VALUE;
      return {
        patientId: String(r.PATIENT || "").trim(),
        date: toDate(r.DATE),
        category: (r.CATEGORY || "unknown").toLowerCase().trim(),
        description: (r.DESCRIPTION || "").trim(),
        value: rawValue !== undefined ? String(rawValue) : null,
        valueNumeric: toNumber(rawValue),
        units: r.UNITS || null,
      };
    })
    .filter((d) => d.patientId && d.date && d.description);

  if (docs.length === 0) return { total: rows.length, inserted: 0 };
  const CHUNK = 5000;
  let inserted = 0;
  for (let i = 0; i < docs.length; i += CHUNK) {
    const res = await Observation.insertMany(docs.slice(i, i + CHUNK), { ordered: false });
    inserted += res.length;
  }
  return { total: rows.length, inserted };
}

module.exports = { importObservations };
