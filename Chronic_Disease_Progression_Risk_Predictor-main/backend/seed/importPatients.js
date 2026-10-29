const Patient = require("../models/Patient");
const { readCsvUpper, toDate, toNumber } = require("./csvUtils");

async function importPatients(filePath) {
  const rows = await readCsvUpper(filePath);
  const ops = rows.map((r) => {
    const patientId = String(r.ID || r.Id || "").trim();
    return {
      updateOne: {
        filter: { patientId },
        update: {
          $set: {
            patientId,
            birthDate: toDate(r.BIRTHDATE),
            deathDate: toDate(r.DEATHDATE),
            gender: (r.GENDER || "U").toUpperCase(),
            marital: r.MARITAL || null,
            race: r.RACE || null,
            ethnicity: r.ETHNICITY || null,
            income: toNumber(r.INCOME),
            city: r.CITY || null,
            state: r.STATE || null,
            zip: r.ZIP || null,
          },
        },
        upsert: true,
      },
    };
  }).filter((op) => op.updateOne.filter.patientId);

  if (ops.length === 0) return { inserted: 0, total: rows.length };
  const result = await Patient.bulkWrite(ops, { ordered: false });
  return {
    total: rows.length,
    upserted: result.upsertedCount,
    modified: result.modifiedCount,
  };
}

module.exports = { importPatients };
