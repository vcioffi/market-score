import { Tooltip } from "./Tooltip";

interface ScoreCardProps {
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "warning" | "danger";
  tooltip?: string;
}

export function ScoreCard({ label, value, tone = "neutral", tooltip }: ScoreCardProps) {
  return (
    <article className={`score-card ${tone}`}>
      <p className="score-label">
        {tooltip ? <Tooltip text={tooltip}>{label}</Tooltip> : label}
      </p>
      <p className="score-value">{value}</p>
    </article>
  );
}
