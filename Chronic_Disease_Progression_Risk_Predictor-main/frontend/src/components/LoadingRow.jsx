export default function LoadingRow({ label = "Loading\u2026" }) {
  return (
    <div className="loading-row">
      <span className="spinner" />
      {label}
    </div>
  );
}
