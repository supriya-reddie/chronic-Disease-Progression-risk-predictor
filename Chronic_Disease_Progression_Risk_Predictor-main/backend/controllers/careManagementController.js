const Prediction = require("../models/Prediction");
const { ApiError } = require("../middleware/errorHandler");

async function latestPredictionsMap() {
  const latest = await Prediction.aggregate([
    { $sort: { patientId: 1, predictionDate: -1 } },
    { $group: { _id: "$patientId", doc: { $first: "$$ROOT" } } },
  ]);
  return latest.map((l) => l.doc);
}

function priorityFor(pred) {
  if (pred.acuteRisk === "HIGH" || pred.progressionRisk === "HIGH") return "HIGH";
  if (pred.acuteRisk === "MEDIUM" || pred.progressionRisk === "MEDIUM") return "MEDIUM";
  return "LOW";
}

async function getQueue(req, res) {
  const preds = await latestPredictionsMap();
  const queue = preds
    .filter((p) => p.acuteRisk !== "LOW" || p.progressionRisk !== "LOW")
    .map((p) => {
      const acuteTop = p.acuteTopFactors?.[0]?.label || p.acuteTopFactors?.[0]?.feature;
      const progTop = p.progressionTopFactors?.[0]?.label || p.progressionTopFactors?.[0]?.feature;
      const mainDriver = p.acuteRisk === "HIGH" ? acuteTop : p.progressionRisk === "HIGH" ? progTop : acuteTop || progTop;
      return {
        id: p._id,
        patientId: p.patientId,
        priority: priorityFor(p),
        acuteRisk: p.acuteRisk,
        progressionRisk: p.progressionRisk,
        mainDriver: mainDriver || "Not available",
        recommendedAction: p.recommendations?.[0] || "Continue routine monitoring",
        recommendations: p.recommendations,
        status: p.careStatus || "Pending",
      };
    })
    .sort((a, b) => {
      const order = { HIGH: 0, MEDIUM: 1, LOW: 2 };
      return order[a.priority] - order[b.priority];
    });

  res.json({ queue, count: queue.length });
}

async function updateStatus(req, res) {
  const { predictionId } = req.params;
  const { status } = req.body;
  const allowed = ["Pending", "Outreach Scheduled", "In Progress", "Completed"];
  if (!allowed.includes(status)) {
    throw new ApiError(400, "Invalid status. Must be one of: " + allowed.join(", "));
  }
  const updated = await Prediction.findByIdAndUpdate(predictionId, { careStatus: status }, { new: true });
  if (!updated) throw new ApiError(404, "Prediction record not found");
  res.json(updated);
}

module.exports = { getQueue, updateStatus };
