import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  act,
  render,
  screen,
  fireEvent,
  waitFor,
} from '@testing-library/react';
import { QrScanner } from './QrScanner';

const { startMock, stopMock, clearMock } = vi.hoisted(() => ({
  startMock: vi.fn(),
  stopMock: vi.fn(),
  clearMock: vi.fn(),
}));

vi.mock('html5-qrcode', () => ({
  Html5Qrcode: vi.fn().mockImplementation(function () {
    return { start: startMock, stop: stopMock, clear: clearMock };
  }),
}));

const VALID_CODE = 'LW:D0:1122334455667788:AABBCCDDEEFF0011:AABB1122';

type DecodeCallback = (text: string) => void | Promise<void>;

function captureDecodeCallback(): () => DecodeCallback {
  let callback: DecodeCallback = () => {};
  startMock.mockImplementation(
    (_device: unknown, _config: unknown, onSuccess: DecodeCallback) => {
      callback = onSuccess;
      return Promise.resolve();
    },
  );
  return () => callback;
}

describe('QrScanner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    startMock.mockResolvedValue(undefined);
    stopMock.mockResolvedValue(undefined);
    clearMock.mockReturnValue(undefined);
  });

  it('renderiza botões Iniciar Scanner e Cancelar', () => {
    render(<QrScanner onDecoded={vi.fn()} onClose={vi.fn()} />);
    expect(
      screen.getByRole('button', { name: /Iniciar Scanner/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Cancelar/i }),
    ).toBeInTheDocument();
  });

  it('clique em Iniciar chama start do scanner', async () => {
    render(<QrScanner onDecoded={vi.fn()} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Iniciar Scanner/i }));
    await waitFor(() => {
      expect(startMock).toHaveBeenCalledTimes(1);
    });
  });

  it('erro de permissão de câmera exibe Alert amigável e estado error', async () => {
    startMock.mockRejectedValueOnce(new Error('NotAllowedError'));
    render(<QrScanner onDecoded={vi.fn()} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Iniciar Scanner/i }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Não foi possível acessar a câmera/i);
    expect(
      screen.getByRole('button', { name: /Iniciar Scanner/i }),
    ).toBeInTheDocument();
  });

  it('QR TR005 lido pela câmera chama onDecoded com parser real e libera câmera', async () => {
    const onDecoded = vi.fn();
    const getCallback = captureDecodeCallback();
    render(<QrScanner onDecoded={onDecoded} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Iniciar Scanner/i }));
    await waitFor(() => expect(startMock).toHaveBeenCalled());

    await act(async () => {
      await getCallback()(VALID_CODE);
    });

    expect(onDecoded).toHaveBeenCalledWith({
      schemaId: 'D0',
      joinEUI: '1122334455667788',
      devEUI: 'AABBCCDDEEFF0011',
      profileId: 'AABB1122',
    });
    expect(stopMock).toHaveBeenCalled();
    expect(clearMock).toHaveBeenCalled();
  });

  it('QR inválido lido pela câmera exibe Alert e mantém scanner ativo', async () => {
    const onDecoded = vi.fn();
    const getCallback = captureDecodeCallback();
    render(<QrScanner onDecoded={onDecoded} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Iniciar Scanner/i }));
    await waitFor(() => expect(startMock).toHaveBeenCalled());

    await act(async () => {
      await getCallback()('codigo-que-nao-e-tr005');
    });

    const alert = await screen.findByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(onDecoded).not.toHaveBeenCalled();
    expect(stopMock).not.toHaveBeenCalled();
  });

  it('QR válido colado manualmente chama onDecoded com campos parseados', async () => {
    const onDecoded = vi.fn();
    render(<QrScanner onDecoded={onDecoded} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Colar código manualmente/i), {
      target: { value: VALID_CODE },
    });
    fireEvent.click(screen.getByRole('button', { name: /Usar código/i }));
    await waitFor(() => expect(onDecoded).toHaveBeenCalledTimes(1));
    expect(onDecoded).toHaveBeenCalledWith({
      schemaId: 'D0',
      joinEUI: '1122334455667788',
      devEUI: 'AABBCCDDEEFF0011',
      profileId: 'AABB1122',
    });
  });

  it('QR inválido colado exibe Alert e não chama onDecoded', async () => {
    const onDecoded = vi.fn();
    render(<QrScanner onDecoded={onDecoded} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Colar código manualmente/i), {
      target: { value: 'codigo-invalido' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Usar código/i }));
    const alert = await screen.findByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(onDecoded).not.toHaveBeenCalled();
  });

  it('Cancelar chama onClose', () => {
    const onClose = vi.fn();
    render(<QrScanner onDecoded={vi.fn()} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /Cancelar/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
