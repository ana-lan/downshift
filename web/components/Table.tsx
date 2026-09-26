import type { ReactNode } from "react";

interface TableProps {
  headers: string[];
  children: ReactNode;
  minWidth?: number;
}

export function Table({ headers, children, minWidth }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table
        className="w-full text-xs sm:text-sm font-mono"
        style={minWidth ? { minWidth: `${minWidth}px` } : undefined}
      >
        <thead>
          <tr className="border-b border-line">
            {headers.map((h, i) => (
              <th
                key={i}
                className="text-left px-3 py-2.5 text-[11px] uppercase tracking-wider font-normal text-subtle whitespace-nowrap"
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
