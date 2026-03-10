interface TickerSearchProps {
  query: string;
  onChange: (value: string) => void;
}

export function TickerSearch({ query, onChange }: TickerSearchProps) {
  return (
    <div className="search-box">
      <input
        aria-label="Search ticker"
        placeholder="Search ticker or company"
        type="text"
        value={query}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
