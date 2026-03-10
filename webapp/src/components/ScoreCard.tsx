interface ScoreCardProps {
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "warning" | "danger";
}

export function ScoreCard({ label, value, tone = "neutral" }: ScoreCardProps) {
  return (
    <article className={`score-card ${tone}`}>
      <p className="score-label">{label}</p>
      <p className="score-value">{value}</p>
    </article>
  );
}
