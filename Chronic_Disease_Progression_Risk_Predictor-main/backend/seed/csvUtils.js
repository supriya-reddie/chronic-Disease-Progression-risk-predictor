const fs = require("fs");
const path = require("path");
const { parse } = require("csv-parse");

/**
 * Streams a CSV file and returns rows as objects with UPPERCASE, trimmed
 * column names - mirrors the header normalization used by the original
 * chronicare_model.py loaders so downstream field lookups match exactly.
 */
function readCsvUpper(filePath) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(filePath)) {
      return reject(new Error("CSV file not found: " + filePath));
    }
    const rows = [];
    fs.createReadStream(filePath)
      .pipe(parse({ columns: (header) => header.map((h) => h.trim().toUpperCase()), skip_empty_lines: true, trim: true }))
      .on("data", (row) => rows.push(row))
      .on("end", () => resolve(rows))
      .on("error", (err) => reject(err));
  });
}

function toDate(value) {
  if (!value || value === "") return null;
  const d = new Date(value);
  return isNaN(d.getTime()) ? null : d;
}

function toNumber(value) {
  if (value === undefined || value === null || value === "") return null;
  const n = Number(value);
  return isNaN(n) ? null : n;
}

function resolveDataFile(dataDir, filename) {
  const candidates = [filename];
  return candidates.map((f) => path.join(dataDir, f)).find((p) => fs.existsSync(p)) || path.join(dataDir, filename);
}

module.exports = { readCsvUpper, toDate, toNumber, resolveDataFile };
