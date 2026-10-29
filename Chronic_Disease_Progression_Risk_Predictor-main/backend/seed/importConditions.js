const Condition = require("../models/Condition");
const { readCsvUpper, toDate } = require("./csvUtils");

async function importConditions(filePath) {
  const rows = await readCsvUpper(filePath);
  await Condition.deleteMany({}); // full refresh on each import run
  const docs = rows
    .map((r) => ({
      patientId: String(r.PATIENT || "").trim(),
      start: toDate(r.START),
      stop: toDate(r.STOP),
      code: r.CODE || null,
      description: (r.DESCRIPTION || "").trim(),
    }))
    .filter((d) => d.patientId && d.start && d.description);

  if (docs.length === 0) return { total: rows.length, inserted: 0 };
  const CHUNK = 5000;
  let inserted = 0;
  for (let i = 0; i < docs.length; i += CHUNK) {
    const chunk = docs.slice(i, i + CHUNK);
    const res = await Condition.insertMany(chunk, { ordered: false });
    inserted += res.length;
  }
  return { total: rows.length, inserted };
}

module.exports = { importConditions };
