import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from 'vitest';
import { act, render, screen } from '@testing-library/react';
import {
  MAX_CONSECUTIVE_FAILURES,
  PROVISIONING_POLL_INTERVAL_MS,
  useProvisioningStatus,
} from './useProvisioningStatus';
import { applicationService } from '../services/app';

vi.mock('../services/app', () => ({
  applicationService: { getStatus: vi.fn() },
}));

const mockedGetStatus = applicationService.getStatus as unknown as Mock;

function Probe({ appId }: { appId: string }) {
  const { status, loading, error } = useProvisioningStatus(appId);
  return (
    <div>
      <span data-testid="status">{status ?? 'null'}</span>
      <span data-testid="loading">{loading ? 'loading' : 'idle'}</span>
      <span data-testid="error">{error ?? 'none'}</span>
    </div>
  );
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe('useProvisioningStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => vi.useRealTimers());

  it('polls immediately on mount', async () => {
    mockedGetStatus.mockResolvedValue('PENDING');

    render(<Probe appId="app-1" />);

    expect(mockedGetStatus).toHaveBeenCalledTimes(1);
    expect(mockedGetStatus).toHaveBeenCalledWith('app-1');

    await advance(0);

    expect(screen.getByTestId('status')).toHaveTextContent('PENDING');
  });

  it('keeps polling every 3s while pending or provisioning', async () => {
    mockedGetStatus
      .mockResolvedValueOnce('PENDING')
      .mockResolvedValueOnce('PROVISIONING')
      .mockResolvedValueOnce('RUNNING');

    render(<Probe appId="app-1" />);

    await advance(0);
    expect(screen.getByTestId('status')).toHaveTextContent('PENDING');

    await advance(PROVISIONING_POLL_INTERVAL_MS);
    expect(screen.getByTestId('status')).toHaveTextContent('PROVISIONING');

    await advance(PROVISIONING_POLL_INTERVAL_MS);
    expect(screen.getByTestId('status')).toHaveTextContent('RUNNING');
    expect(mockedGetStatus).toHaveBeenCalledTimes(3);
  });

  it('stops polling when the status reaches RUNNING', async () => {
    mockedGetStatus.mockResolvedValue('RUNNING');

    render(<Probe appId="app-1" />);

    await advance(0);
    expect(mockedGetStatus).toHaveBeenCalledTimes(1);

    await advance(PROVISIONING_POLL_INTERVAL_MS * 3);

    expect(mockedGetStatus).toHaveBeenCalledTimes(1);
  });

  it('stops polling when the status reaches ERROR', async () => {
    mockedGetStatus.mockResolvedValue('ERROR');

    render(<Probe appId="app-1" />);

    await advance(0);

    expect(mockedGetStatus).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('status')).toHaveTextContent('ERROR');
  });

  it('keeps polling and clears error after a transient failure', async () => {
    mockedGetStatus
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce('PENDING');

    render(<Probe appId="app-1" />);

    await advance(0);
    expect(screen.getByTestId('error')).not.toHaveTextContent('none');
    expect(mockedGetStatus).toHaveBeenCalledTimes(1);

    await advance(PROVISIONING_POLL_INTERVAL_MS);

    expect(screen.getByTestId('error')).toHaveTextContent('none');
    expect(screen.getByTestId('status')).toHaveTextContent('PENDING');
  });

  it('stops and signals after consecutive failures', async () => {
    mockedGetStatus.mockRejectedValue(new Error('offline'));

    render(<Probe appId="app-1" />);

    await advance(0);
    await advance(PROVISIONING_POLL_INTERVAL_MS * (MAX_CONSECUTIVE_FAILURES - 1));

    expect(mockedGetStatus).toHaveBeenCalledTimes(MAX_CONSECUTIVE_FAILURES);
    expect(screen.getByTestId('error')).toHaveTextContent('offline');

    await advance(PROVISIONING_POLL_INTERVAL_MS * 2);

    expect(mockedGetStatus).toHaveBeenCalledTimes(MAX_CONSECUTIVE_FAILURES);
  });

  it('discards a resolved request after unmount', async () => {
    let resolve!: (value: string) => void;
    mockedGetStatus.mockReturnValue(
      new Promise<string>((r) => {
        resolve = r;
      }),
    );

    const { unmount } = render(<Probe appId="app-1" />);

    expect(mockedGetStatus).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      resolve('RUNNING');
      await Promise.resolve();
    });

    expect(screen.queryByTestId('status')).toBeNull();
  });

  it('discards a late resolution from the previous application', async () => {
    let resolve!: (value: string) => void;
    mockedGetStatus.mockReturnValueOnce(
      new Promise<string>((r) => {
        resolve = r;
      }),
    );
    mockedGetStatus.mockResolvedValue('PROVISIONING');

    const { rerender } = render(<Probe appId="app-1" />);

    rerender(<Probe appId="app-2" />);

    await act(async () => {
      resolve('RUNNING');
      await Promise.resolve();
    });
    await advance(0);

    expect(screen.getByTestId('status')).toHaveTextContent('PROVISIONING');
  });

  it('does nothing without an application id', async () => {
    render(<Probe appId="" />);

    await advance(PROVISIONING_POLL_INTERVAL_MS * 3);

    expect(mockedGetStatus).not.toHaveBeenCalled();
  });

  it('restarts polling when the application changes', async () => {
    mockedGetStatus.mockResolvedValue('PENDING');

    const { rerender } = render(<Probe appId="app-1" />);

    await advance(0);
    expect(mockedGetStatus).toHaveBeenLastCalledWith('app-1');

    rerender(<Probe appId="app-2" />);
    expect(screen.getByTestId('status')).toHaveTextContent('null');

    await advance(0);
    expect(mockedGetStatus).toHaveBeenLastCalledWith('app-2');
  });
});
