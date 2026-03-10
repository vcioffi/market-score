import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

interface LayoutProps {
  children: ReactNode;
  runDate?: string;
}

export function Layout({ children, runDate }: LayoutProps) {
  const location = useLocation();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <p className="eyebrow">Weekly Equity Intelligence</p>
          <h1>Market Score</h1>
        </div>
        <nav className="topnav">
          <Link className={location.pathname === "/" ? "active" : ""} to="/">
            Dashboard
          </Link>
        </nav>
        <div className="run-date">Run: {runDate ?? "n/a"}</div>
      </header>
      <main>{children}</main>
    </div>
  );
}
