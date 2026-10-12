import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { TelemetryLineChart } from './TelemetryLineChart';

const data = [
  { time: '2026-01-01T00:00:00Z', value: 20 },
  { time: '2026-01-01T00:01:00Z', value: 22 },
];

describe('TelemetryLineChart', () => {
  it('renders a line path for the provided series', () => {
    const { container } = render(
      <TelemetryLineChart data={data} label="temperature" width={800} />,
    );

    expect(container.querySelector('.recharts-line-curve')).not.toBeNull();
  });

  it('does not throw when data is empty', () => {
    const { container } = render(<TelemetryLineChart data={[]} width={800} />);

    expect(container.querySelector('svg')).not.toBeNull();
  });
});
