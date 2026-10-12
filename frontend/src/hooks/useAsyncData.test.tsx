import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useAsyncData } from './useAsyncData';

function Probe({
  fn,
  showReload = false,
}: {
  fn: () => Promise<string>;
  showReload?: boolean;
}) {
  const { data, error, loading, reload } = useAsyncData(fn, []);
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
});
