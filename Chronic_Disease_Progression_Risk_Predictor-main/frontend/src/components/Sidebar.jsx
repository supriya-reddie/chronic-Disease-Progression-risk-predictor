import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "\u25A6", end: true },
  { to: "/patients", label: "Patients", icon: "\u25A4" },
  { to: "/risk-analytics", label: "Risk Analytics", icon: "\u25B2" },
  { to: "/high-risk", label: "High-Risk Patients", icon: "\u26A0" },
  { to: "/care-management", label: "Care Management", icon: "\u2295" },
  { to: "/prediction-history", label: "Prediction History", icon: "\u27F3" },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">ChroniCare Intelligence</div>
        <div className="sidebar-brand-sub">Payer Risk Platform</div>
        <div className="risk-spectrum" />
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
          >
            <span aria-hidden="true">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        Acute &amp; progression risk models
        <br />
        frozen &middot; scored on demand
      </div>
    </aside>
  );
}
