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
  PROVISIONING_POLL_INTERVAL_MS,
  useProvisioningStatus,
} from './useProvisioningStatus';
import { applicationService } from '../services/app';

vi.mock('../services/app', () => ({
  applicationService: { getStatus: vi.fn() },
}));

const mockedGetStatus = applicationService.getStatus as unknown as Mock;

function Probe({ appId }: { appId: string }) {
  const { status } = useProvisioningStatus(appId);
  return <span data-testid="status">{status ?? 'null'}</span>;
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

  it('starts without a status and polls after the interval', async () => {
    mockedGetStatus.mockResolvedValue('PENDING');

    render(<Probe appId="app-1" />);

    expect(screen.getByTestId('status')).toHaveTextContent('null');

    await advance(PROVISIONING_POLL_INTERVAL_MS);

    expect(mockedGetStatus).toHaveBeenCalledWith('app-1');
    expect(screen.getByTestId('status')).toHaveTextContent('PENDING');
  });

  it('keeps polling every 3s while pending or provisioning', async () => {
    mockedGetStatus
      .mockResolvedValueOnce('PENDING')
      .mockResolvedValueOnce('PROVISIONING')
      .mockResolvedValueOnce('RUNNING');

    render(<Probe appId="app-1" />);

    await advance(PROVISIONING_POLL_INTERVAL_MS);
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

    await advance(PROVISIONING_POLL_INTERVAL_MS);
    expect(mockedGetStatus).toHaveBeenCalledTimes(1);

    await advance(PROVISIONING_POLL_INTERVAL_MS * 3);

    expect(mockedGetStatus).toHaveBeenCalledTimes(1);
  });

  it('stops polling when the status reaches ERROR', async () => {
    mockedGetStatus.mockResolvedValue('ERROR');

    render(<Probe appId="app-1" />);

    await advance(PROVISIONING_POLL_INTERVAL_MS);
    expect(mockedGetStatus).toHaveBeenCalledTimes(1);

    await advance(PROVISIONING_POLL_INTERVAL_MS * 3);

    expect(mockedGetStatus).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('status')).toHaveTextContent('ERROR');
  });

  it('keeps polling after a request error', async () => {
    mockedGetStatus.mockRejectedValue(new Error('offline'));

    render(<Probe appId="app-1" />);

    await advance(PROVISIONING_POLL_INTERVAL_MS * 2);

    expect(mockedGetStatus).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId('status')).toHaveTextContent('null');
  });

  it('clears the interval on unmount', async () => {
    mockedGetStatus.mockResolvedValue('PENDING');

    const { unmount } = render(<Probe appId="app-1" />);

    await advance(PROVISIONING_POLL_INTERVAL_MS);
    expect(mockedGetStatus).toHaveBeenCalledTimes(1);

    unmount();
    await advance(PROVISIONING_POLL_INTERVAL_MS * 3);

    expect(mockedGetStatus).toHaveBeenCalledTimes(1);
  });

  it('does nothing without an application id', async () => {
    render(<Probe appId="" />);

    await advance(PROVISIONING_POLL_INTERVAL_MS * 3);

    expect(mockedGetStatus).not.toHaveBeenCalled();
  });

  it('restarts polling when the application changes', async () => {
    mockedGetStatus.mockResolvedValue('PENDING');

    const { rerender } = render(<Probe appId="app-1" />);

    await advance(PROVISIONING_POLL_INTERVAL_MS);
    expect(mockedGetStatus).toHaveBeenLastCalledWith('app-1');

    rerender(<Probe appId="app-2" />);
    expect(screen.getByTestId('status')).toHaveTextContent('null');

    await advance(PROVISIONING_POLL_INTERVAL_MS);
    expect(mockedGetStatus).toHaveBeenLastCalledWith('app-2');
  });
});
