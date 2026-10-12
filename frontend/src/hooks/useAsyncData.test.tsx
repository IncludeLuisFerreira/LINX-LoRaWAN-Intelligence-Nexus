import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useAsyncData } from './useAsyncData';

function Probe({
  fn,
  showReload = false,
  dep = 0,
}: {
  fn: () => Promise<string>;
  showReload?: boolean;
  dep?: number;
}) {
  const { data, error, loading, reload } = useAsyncData(fn, [dep]);
  return (
    <div>
      <span data-testid="state">
        {loading ? 'loading' : error || data || 'empty'}
      </span>
      {showReload && <button onClick={reload}>reload</button>}
    </div>
  );
}

describe('useAsyncData', () => {
  it('starts loading and resolves with data', async () => {
    render(<Probe fn={async () => 'ok'} />);

    expect(screen.getByTestId('state')).toHaveTextContent('loading');
    await waitFor(() =>
      expect(screen.getByTestId('state')).toHaveTextContent('ok'),
    );
  });

  it('surfaces the error message when the fetch rejects', async () => {
    render(<Probe fn={async () => Promise.reject(new Error('boom'))} />);

    await waitFor(() =>
      expect(screen.getByTestId('state')).toHaveTextContent('boom'),
    );
  });

  it('refetches when reload is called', async () => {
    const fn = vi
      .fn<() => Promise<string>>()
      .mockResolvedValueOnce('first')
      .mockResolvedValueOnce('second');

    render(<Probe fn={fn} showReload />);
    await waitFor(() =>
      expect(screen.getByTestId('state')).toHaveTextContent('first'),
    );

    await userEvent.click(screen.getByRole('button', { name: 'reload' }));

    await waitFor(() =>
      expect(screen.getByTestId('state')).toHaveTextContent('second'),
    );
  });

  it('ignores a stale response that resolves after a newer one', async () => {
    let resolveFirst: (value: string) => void = () => {};
    let resolveSecond: (value: string) => void = () => {};
    let call = 0;
    const fn = () => {
      call += 1;
      return new Promise<string>((resolve) => {
        if (call === 1) resolveFirst = resolve;
        else resolveSecond = resolve;
      });
    };

    const { rerender } = render(<Probe fn={fn} dep={1} />);
    rerender(<Probe fn={fn} dep={2} />);

    resolveSecond('new');
    await waitFor(() =>
      expect(screen.getByTestId('state')).toHaveTextContent('new'),
    );

    resolveFirst('old');
    await waitFor(() =>
      expect(screen.getByTestId('state')).toHaveTextContent('new'),
    );
  });
});
