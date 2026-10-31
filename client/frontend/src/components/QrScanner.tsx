import { useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';
import { parseTr005, Tr005ParseError, type Tr005Data } from '../utils/tr005';
import { Button } from './ui/Button';
import { Alert } from './ui/Alert';
import { Input } from './ui/Input';

interface QrScannerProps {
  /** Callback quando QR válido é decodificado */
  onDecoded: (data: Tr005Data) => void;
  /** Callback para fechar o scanner */
  onClose: () => void;
}

type ScannerState = 'idle' | 'starting' | 'scanning' | 'error';

export function QrScanner({ onDecoded, onClose }: QrScannerProps) {
  const [state, setState] = useState<ScannerState>('idle');
  const [error, setError] = useState('');
  const [manualCode, setManualCode] = useState('');
  const scannerRef = useRef<Html5Qrcode | null>(null);
  // Último texto decodificado: evita reprocessar o mesmo QR a cada frame.
  const handledTextRef = useRef<string | null>(null);
  // Sinaliza desmontagem para abortar um start() que ainda está pendente.
  const cancelledRef = useRef(false);

  async function stopScanner() {
    if (scannerRef.current) {
      try {
        await scannerRef.current.stop();
        scannerRef.current.clear();
      } catch {
        // Scanner já estava parado
      }
      scannerRef.current = null;
    }
  }

  async function startScanner() {
    setState('starting');
    setError('');
    handledTextRef.current = null;
    cancelledRef.current = false;

    try {
      const scanner = new Html5Qrcode('qr-reader-container');
      scannerRef.current = scanner;

      await scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: 250 },
        async (decodedText: string) => {
          // html5-qrcode dispara este callback a cada frame; ignora repetições.
          if (handledTextRef.current === decodedText) return;
          handledTextRef.current = decodedText;

          try {
            const data = parseTr005(decodedText);
            await stopScanner();
            onDecoded(data);
          } catch (err) {
            if (err instanceof Tr005ParseError) {
              setError(err.message);
            } else {
              setError('Erro ao processar QR Code.');
            }
          }
        },
        () => {
          // Falha de leitura — ignora, continua tentando
        },
      );

      // Desmontou durante o prompt de permissão: desliga a câmera e libera.
      if (cancelledRef.current) {
        await scanner.stop().catch(() => {});
        scanner.clear();
        return;
      }

      setState('scanning');
    } catch {
      setState('error');
      setError(
        'Não foi possível acessar a câmera. Verifique as permissões do navegador.',
      );
    }
  }

  async function handleManualSubmit() {
    setError('');
    try {
      const data = parseTr005(manualCode);
      await stopScanner();
      onDecoded(data);
    } catch (err) {
      if (err instanceof Tr005ParseError) {
        setError(err.message);
      } else {
        setError('Erro ao processar o código.');
      }
    }
  }

  // Cleanup ao desmontar
  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      stopScanner();
    };
  }, []);

  async function handleStop() {
    await stopScanner();
    handledTextRef.current = null;
    setError('');
    setState('idle');
  }

  return (
    <div className="space-y-4">
      <div
        id="qr-reader-container"
        className="w-full min-h-[250px] bg-gray-100 rounded-lg overflow-hidden"
      />

      {error && <Alert variant="error">{error}</Alert>}

      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          handleManualSubmit();
        }}
      >
        <Input
          label="Colar código manualmente"
          name="manual-code"
          placeholder="LW:D0:..."
          value={manualCode}
          onChange={(e) => setManualCode(e.target.value)}
        />
        <Button type="submit" variant="secondary" disabled={!manualCode.trim()}>
          Usar código
        </Button>
      </form>

      <div className="flex gap-2 justify-end">
        <Button variant="secondary" onClick={onClose}>
          Cancelar
        </Button>
        {state === 'scanning' ? (
          <Button variant="secondary" onClick={handleStop}>
            Parar
          </Button>
        ) : (
          <Button onClick={startScanner} loading={state === 'starting'}>
            {state === 'starting' ? 'Iniciando...' : 'Iniciar Scanner'}
          </Button>
        )}
      </div>
    </div>
  );
}
