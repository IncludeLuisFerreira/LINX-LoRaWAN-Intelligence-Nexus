import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UuidDisplay } from './UuidDisplay';

const uuid = '123e4567-e89b-12d3-a456-426614174000';
const writeText = vi.fn<() => Promise<void>>();

function setClipboard(value: unknown) {
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value,
  });
}

describe('UuidDisplay', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    writeText.mockReset();
    writeText.mockResolvedValue(undefined);
    setClipboard({ writeText });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('renders the UUID in monospace', () => {
    render(<UuidDisplay value={uuid} />);

    expect(screen.getByText(uuid)).toHaveClass('font-mono');
  });

  it('copies the UUID and restores the label after the feedback delay', async () => {
    render(<UuidDisplay value={uuid} />);

    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: `Copiar UUID ${uuid}` }),
      );
    });

    expect(writeText).toHaveBeenCalledWith(uuid);
    expect(screen.getByRole('button')).toHaveTextContent('Copiado!');

    act(() => {
      vi.advanceTimersByTime(1500);
    });

    expect(screen.getByRole('button')).toHaveTextContent('Copiar');
  });

  it('shows an error when the clipboard write fails', async () => {
    writeText.mockRejectedValueOnce(new Error('permission denied'));
    render(<UuidDisplay value={uuid} />);

    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: `Copiar UUID ${uuid}` }),
      );
    });

    expect(screen.getByRole('button')).toHaveTextContent('Falha ao copiar');
  });

  it('shows an error when the clipboard API is unavailable', async () => {
    setClipboard(undefined);
    render(<UuidDisplay value={uuid} />);

    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: `Copiar UUID ${uuid}` }),
      );
    });

    expect(screen.getByRole('button')).toHaveTextContent('Falha ao copiar');
  });
});
