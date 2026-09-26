interface CodeBlockProps {
  code: string;
  label?: string;
}

export function CodeBlock({ code, label }: CodeBlockProps) {
  return (
    <div>
      {label && (
        <p className="text-[11px] font-mono uppercase tracking-wider text-subtle mb-2">{label}</p>
      )}
      <div className="rounded-lg border border-line bg-card px-4 py-3.5 overflow-x-auto text-xs font-mono text-text whitespace-pre">
        {code}
      </div>
    </div>
  );
}
