import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { useTelemetrySocket } from './useTelemetrySocket';
import type { TelemetryItem } from '../services/telemetry';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn();
  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }
}

function Probe({
  appId,
  onMessage,
}: {
  appId: string;
  onMessage: (item: TelemetryItem) => void;
}) {
  useTelemetrySocket(appId, onMessage);
  return null;
}

describe('useTelemetrySocket', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    vi.stubGlobal('location', { protocol: 'http:', host: 'localhost' });
  });

  afterEach(() => vi.unstubAllGlobals());

  it('opens the socket at /ws/telemetry/{appId}', () => {
    render(<Probe appId="app-1" onMessage={vi.fn()} />);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toBe(
      'ws://localhost/ws/telemetry/app-1',
    );
  });

  it('delivers a parsed item to the callback', () => {
    const onMessage = vi.fn();
    render(<Probe appId="app-1" onMessage={onMessage} />);
    FakeWebSocket.instances[0].onmessage?.({
      data: '{"time":"t","dev_eui":"aabb","payload":{}}',
    });
    expect(onMessage).toHaveBeenCalledWith(
      expect.objectContaining({ time: 't', dev_eui: 'aabb' }),
    );
  });

  it('ignores invalid JSON without calling the callback', () => {
    const onMessage = vi.fn();
    render(<Probe appId="app-1" onMessage={onMessage} />);
    FakeWebSocket.instances[0].onmessage?.({ data: '{not json' });
    expect(onMessage).not.toHaveBeenCalled();
  });

  it('closes the socket on unmount', () => {
    const { unmount } = render(<Probe appId="app-1" onMessage={vi.fn()} />);
    const socket = FakeWebSocket.instances[0];
    unmount();
    expect(socket.close).toHaveBeenCalled();
  });

  it('reopens with a new url when appId changes', () => {
    const { rerender } = render(<Probe appId="app-1" onMessage={vi.fn()} />);
    const first = FakeWebSocket.instances[0];

    rerender(<Probe appId="app-2" onMessage={vi.fn()} />);

    expect(first.close).toHaveBeenCalled();
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[1].url).toBe(
      'ws://localhost/ws/telemetry/app-2',
    );
  });

  it('does not throw when the socket errors', () => {
    render(<Probe appId="app-1" onMessage={vi.fn()} />);
    expect(() => FakeWebSocket.instances[0].onerror?.()).not.toThrow();
  });
});
