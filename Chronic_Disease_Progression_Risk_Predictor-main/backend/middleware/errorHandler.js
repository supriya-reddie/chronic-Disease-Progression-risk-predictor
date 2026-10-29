function notFound(req, res, next) {
  res.status(404).json({ error: "Not found", path: req.originalUrl });
}

// Central error handler. Keeps messages friendly for the frontend while
// logging full detail server-side.
function errorHandler(err, req, res, next) {
  console.error("[ERROR]", err.message);
  if (process.env.NODE_ENV !== "production") {
    console.error(err.stack);
  }

  if (err.code === "ECONNREFUSED" || err.code === "ECONNABORTED") {
    return res.status(503).json({
      error: "The ML prediction service is unavailable. Please try again shortly.",
      detail: err.message,
    });
  }

  if (err.name === "ValidationError") {
    return res.status(400).json({ error: "Invalid data", detail: err.message });
  }

  if (err.name === "CastError") {
    return res.status(400).json({ error: "Invalid identifier", detail: err.message });
  }

  const status = err.status || err.statusCode || 500;
  res.status(status).json({
    error: err.publicMessage || "Something went wrong on the server.",
    detail: process.env.NODE_ENV === "production" ? undefined : err.message,
  });
}

class ApiError extends Error {
  constructor(status, publicMessage, detail) {
    super(detail || publicMessage);
    this.status = status;
    this.publicMessage = publicMessage;
  }
}

module.exports = { notFound, errorHandler, ApiError };
