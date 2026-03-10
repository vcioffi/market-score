import type { BasketItem } from "../types/api";

interface BasketCardProps {
  items: BasketItem[];
  rationale: string;
}

export function BasketCard({ items, rationale }: BasketCardProps) {
  return (
    <section className="panel basket-panel">
      <div className="panel-header">
        <h3>Best Basket</h3>
      </div>
      <p className="basket-rationale">{rationale}</p>
      <ul className="basket-list">
        {items.map((item) => (
          <li key={item.ticker}>
            <span>{item.ticker}</span>
            <span>{(item.weight * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
