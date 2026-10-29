const mongoose = require("mongoose");

async function connectDB() {
  const uri = process.env.MONGO_URI || "mongodb://localhost:27017/cdprp";
  mongoose.set("strictQuery", true);

  mongoose.connection.on("connected", () => {
    console.log("[MongoDB] connected -> " + uri);
  });
  mongoose.connection.on("error", (err) => {
    console.error("[MongoDB] connection error:", err.message);
  });
  mongoose.connection.on("disconnected", () => {
    console.warn("[MongoDB] disconnected");
  });

  await mongoose.connect(uri, {
    serverSelectionTimeoutMS: 8000,
  });
}

module.exports = { connectDB };
