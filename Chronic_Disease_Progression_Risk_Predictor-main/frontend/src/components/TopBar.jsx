export default function TopBar({ title, subtitle, children }) {
  return (
    <div className="topbar">
      <div>
        <div className="topbar-title">{title}</div>
        {subtitle ? <div className="topbar-sub">{subtitle}</div> : null}
      </div>
      <div>{children}</div>
    </div>
  );
}
