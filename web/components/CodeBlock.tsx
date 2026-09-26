interface CodeBlockProps {
  code: string;
  label?: string;
}

export function CodeBlock({ code, label }: CodeBlockProps) {
  return (
    <div>
      {label && (
        <p className="text-xs font-mono text-subtle mb-1">{label}</p>
      )}
      <div className="rounded-xl border border-line bg-card p-4 overflow-x-auto text-xs font-mono text-muted whitespace-pre">
        {code}
      </div>
    </div>
  );
}
