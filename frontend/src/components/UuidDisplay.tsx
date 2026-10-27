import { useState } from 'react';

export function UuidDisplay({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error('Erro ao copiar UUID:', err);
    }
  };

  return (
    <span className="font-mono text-sm">
      {value} <button onClick={copy}>{copied ? 'Copiado!' : 'Copiar'}</button>
    </span>
  );
}
