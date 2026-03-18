import { useMemo } from "react";
import { Link } from "react-router-dom";

import type { RankingEntry } from "../types/api";
import { Tooltip } from "./Tooltip";
import { T } from "../utils/tooltips";

interface RankingTableProps {
  items: RankingEntry[];
  sectorFilter: string;
}

export function RankingTable({ items, sectorFilter }: RankingTableProps) {
  const filtered = useMemo(() => {
    if (!sectorFilter || sectorFilter === "All") return items;
    return items.filter((item) => item.sector === sectorFilter);
  }, [items, sectorFilter]);

  return (
    <section className="panel">
      <div className="panel-header">
        <h3>Classifica Settimanale</h3>
        <span>{filtered.length} ticker</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Ticker</th>
              <th>Azienda</th>
              <th>Settore</th>
              <th><Tooltip text={T.benefit}>Beneficio</Tooltip></th>
              <th><Tooltip text={T.risk}>Rischio</Tooltip></th>
              <th><Tooltip text={T.confidence}>Fiducia</Tooltip></th>
              <th><Tooltip text={T.composite}>Composito</Tooltip></th>
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
