import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { TelemetryLineChart } from './TelemetryLineChart';

const series = [
  {
    key: 'a',
    label: 'A',
    data: [
      { time: '2026-01-01T00:00:00Z', value: 20 },
      { time: '2026-01-01T00:01:00Z', value: 21 },
    ],
  },
  {
    key: 'b',
    label: 'B',
    data: [
      { time: '2026-01-01T00:00:00Z', value: 22 },
      { time: '2026-01-01T00:01:00Z', value: 23 },
    ],
  },
];

describe('TelemetryLineChart', () => {
  it('renders one line per series', () => {
    const { container } = render(
      <TelemetryLineChart series={series} width={800} />,
    );

    expect(container.querySelectorAll('.recharts-line-curve')).toHaveLength(2);
  });

  it('renders a single line for a single series', () => {
    const { container } = render(
      <TelemetryLineChart series={[series[0]]} width={800} />,
    );

    expect(container.querySelectorAll('.recharts-line-curve')).toHaveLength(1);
  });

  it('does not throw when the series is empty', () => {
    const { container } = render(
      <TelemetryLineChart series={[]} width={800} />,
    );

    expect(container.querySelector('svg')).not.toBeNull();
  });
});
