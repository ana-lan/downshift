import type { ReactNode } from "react";

interface TableProps {
  headers: string[];
  children: ReactNode;
  minWidth?: number;
}

export function Table({ headers, children, minWidth }: TableProps) {
  return (
    <div className="rounded-xl border border-line overflow-x-auto">
      <table
        className="w-full text-xs sm:text-sm font-mono"
        style={minWidth ? { minWidth: `${minWidth}px` } : undefined}
      >
        <thead>
          <tr className="bg-card">
            {headers.map((h, i) => (
              <th
                key={i}
                className="text-left px-3 sm:px-4 py-2 text-subtle font-normal text-xs border-b border-line whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
