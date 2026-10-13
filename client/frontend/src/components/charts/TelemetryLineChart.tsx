import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { mergeSeries, type SeriesInput } from '../../services/telemetry';
import { formatDate } from '../../utils/format';

interface TelemetryLineChartProps {
  series: SeriesInput[];
  height?: number;
  width?: number;
}

const AXIS_COLOR = '#64748b';
const COLORS = [
  '#8884d8',
  '#82ca9d',
  '#ffc658',
  '#ff7300',
  '#00c49f',
  '#d0ed57',
  '#a4de6c',
  '#8dd1e1',
];

function formatTick(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function TelemetryLineChart({
  series,
  height = 320,
  width,
}: TelemetryLineChartProps) {
  const rows = mergeSeries(series);

  const chart = (
    <LineChart
      data={rows}
      height={height}
      width={width}
      margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
    >
      <XAxis
        dataKey="time"
        tickFormatter={formatTick}
        stroke={AXIS_COLOR}
        fontSize={12}
        minTickGap={24}
      />
      <YAxis stroke={AXIS_COLOR} fontSize={12} width={48} />
      <Tooltip labelFormatter={(value) => formatDate(String(value))} />
      <Legend />
      {series.map((entry, index) => (
        <Line
          key={entry.key}
          type="monotone"
          dataKey={entry.key}
          name={entry.label}
          stroke={COLORS[index % COLORS.length]}
          strokeWidth={2}
          dot={false}
          connectNulls
          isAnimationActive={false}
        />
      ))}
    </LineChart>
  );

  if (width) return chart;

  return (
    <div data-testid="telemetry-chart" style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height={height}>
        {chart}
      </ResponsiveContainer>
    </div>
  );
}
