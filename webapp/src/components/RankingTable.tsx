import { useMemo } from "react";
import { Link } from "react-router-dom";

import type { RankingEntry } from "../types/api";

interface RankingTableProps {
  items: RankingEntry[];
  sectorFilter: string;
}

export function RankingTable({ items, sectorFilter }: RankingTableProps) {
  const filtered = useMemo(() => {
    if (!sectorFilter || sectorFilter === "All") {
      return items;
    }
    return items.filter((item) => item.sector === sectorFilter);
  }, [items, sectorFilter]);

  return (
    <section className="panel">
      <div className="panel-header">
        <h3>Weekly Ranking</h3>
        <span>{filtered.length} tickers</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Ticker</th>
              <th>Company</th>
              <th>Sector</th>
              <th>Benefit</th>
              <th>Risk</th>
              <th>Confidence</th>
              <th>Composite</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, index) => (
              <tr key={row.ticker}>
                <td>{index + 1}</td>
                <td>
                  <Link to={`/ticker/${row.ticker}`}>{row.ticker}</Link>
                </td>
                <td>{row.company_name}</td>
                <td>{row.sector}</td>
                <td>{row.benefit_score.toFixed(1)}</td>
                <td>{row.risk_score.toFixed(1)}</td>
                <td>{row.confidence_score.toFixed(1)}</td>
                <td>{row.composite_score.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
