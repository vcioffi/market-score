import type { ReactNode } from "react";

interface TooltipProps {
  text: string;
  children: ReactNode;
}

export function Tooltip({ text, children }: TooltipProps) {
  return (
    <span className="tooltip-wrap">
      {children}
      <span className="tooltip-body">{text}</span>
    </span>
  );
}
