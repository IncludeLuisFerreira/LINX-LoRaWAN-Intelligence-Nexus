import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TelemetryPoint } from '../../services/telemetry';
import { formatDate } from '../../utils/format';

interface TelemetryLineChartProps {
  data: TelemetryPoint[];
  label?: string;
  height?: number;
  width?: number;
}

const AXIS_COLOR = '#64748b';

function formatTick(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function TelemetryLineChart({
  data,
  label = 'Valor',
  height = 320,
  width,
}: TelemetryLineChartProps) {
  const chart = (
    <LineChart
      data={data}
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
      <Line
        type="monotone"
        dataKey="value"
        name={label}
        stroke="#8884d8"
        strokeWidth={2}
        dot={false}
        isAnimationActive={false}
      />
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
