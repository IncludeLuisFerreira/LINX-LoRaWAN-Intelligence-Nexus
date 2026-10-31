import { useEffect, useRef, useState } from 'react';
import { cn } from '../../utils/cn';
import { Button } from './Button';

type CopyStatus = 'idle' | 'copied' | 'error';

interface UuidDisplayProps {
  value: string;
  className?: string;
}

export function UuidDisplay({ value, className }: UuidDisplayProps) {
  const [status, setStatus] = useState<CopyStatus>('idle');
  const timeoutRef = useRef<number | undefined>(undefined);

  useEffect(
    () => () => {
      if (timeoutRef.current !== undefined) {
        window.clearTimeout(timeoutRef.current);
      }
    },
    [],
  );

  function scheduleReset() {
    timeoutRef.current = window.setTimeout(() => setStatus('idle'), 1500);
  }

  async function copy() {
    if (timeoutRef.current !== undefined) {
      window.clearTimeout(timeoutRef.current);
    }

    if (!navigator.clipboard?.writeText) {
      setStatus('error');
      scheduleReset();
      return;
    }

    try {
      await navigator.clipboard.writeText(value);
      setStatus('copied');
    } catch {
      setStatus('error');
    }

    scheduleReset();
  }

  return (
    <span className={cn('inline-flex min-w-0 items-center gap-2', className)}>
      <code className="break-all font-mono text-xs text-slate-700">
        {value}
      </code>
      <Button
        type="button"
        variant="ghost"
        className="shrink-0 px-2 py-1 text-xs"
        aria-label={`Copiar UUID ${value}`}
        onClick={copy}
      >
        {status === 'copied'
          ? 'Copiado!'
          : status === 'error'
            ? 'Falha ao copiar'
            : 'Copiar'}
      </Button>
      <span role="status" aria-live="polite" className="sr-only">
        {status === 'copied'
          ? 'UUID copiado'
          : status === 'error'
            ? 'Falha ao copiar UUID'
            : ''}
      </span>
    </span>
  );
}
