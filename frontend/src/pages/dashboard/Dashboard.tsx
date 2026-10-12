import { useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { deviceService, type DeviceOutput } from '../../services/device';
import {
  telemetryService,
  numericMetrics,
  buildSeries,
  type TelemetryHistory,
  type SeriesInput,
} from '../../services/telemetry';
import { useAsyncData } from '../../hooks/useAsyncData';
import { formatDate } from '../../utils/format';
import { PageHeader } from '../../components/layout/PageHeader';
import { Breadcrumbs } from '../../components/ui/Breadcrumbs';
import { Card } from '../../components/ui/Card';
import { Select } from '../../components/ui/Select';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { TelemetryLineChart } from '../../components/charts/TelemetryLineChart';

const ALL_DEVICES = '__all__';
const EMPTY_HISTORY: TelemetryHistory = { items: [], next_cursor: null };

interface DeviceHistory {
  devEui: string;
  history: TelemetryHistory;
}

async function loadHistories(
  devices: DeviceOutput[],
): Promise<DeviceHistory[]> {
  const results = await Promise.allSettled(
    devices.map((device) => telemetryService.history(device.dev_eui)),
  );
  if (results.length > 0 && results.every((result) => result.status === 'rejected')) {
    throw (results[0] as PromiseRejectedResult).reason;
  }
  return devices.map((device, index) => {
    const result = results[index];
    return {
      devEui: device.dev_eui,
      history:
        result.status === 'fulfilled' ? result.value : EMPTY_HISTORY,
    };
  });
}

export default function Dashboard() {
  const { appId = '' } = useParams();
  const location = useLocation();
  const appName = (location.state as { appName?: string } | null)?.appName;

  const {
    data: devicesData,
    error: devicesError,
    loading: devicesLoading,
    reload: reloadDevices,
  } = useAsyncData(() => deviceService.listByApp(appId), [appId]);

  const devices = devicesData ?? [];
  const [selectedDevEui, setSelectedDevEui] = useState('');
  const [metric, setMetric] = useState('');

  const activeDevEui =
    selectedDevEui === ALL_DEVICES
      ? ALL_DEVICES
      : devices.some((device) => device.dev_eui === selectedDevEui)
        ? selectedDevEui
        : (devices[0]?.dev_eui ?? '');

  const {
    data: history,
    error: historyError,
    loading: historyLoading,
    reload: reloadHistory,
  } = useAsyncData(
    () => {
      if (activeDevEui === ALL_DEVICES) return loadHistories(devices);
      if (activeDevEui)
        return telemetryService
          .history(activeDevEui)
          .then((result) => [{ devEui: activeDevEui, history: result }]);
      return Promise.resolve([] as DeviceHistory[]);
    },
    [appId, activeDevEui, devices.length],
  );

  const entries = history ?? [];
  const items = entries.flatMap((entry) => entry.history.items);
  const metrics = numericMetrics(items);
  const activeMetric = metrics.includes(metric) ? metric : (metrics[0] ?? '');

  const labelFor = (devEui: string) =>
    devices.find((device) => device.dev_eui === devEui)?.nickname ?? devEui;

  let lastReadingTime: string | null = null;
  let latestMs = Number.NEGATIVE_INFINITY;
  for (const item of items) {
    const ms = Date.parse(item.time);
    if (!Number.isNaN(ms) && ms > latestMs) {
      latestMs = ms;
      lastReadingTime = item.time;
    }
  }

  const chartSeries: SeriesInput[] =
    activeDevEui === ALL_DEVICES
      ? entries.map((entry) => ({
          key: entry.devEui,
          label: labelFor(entry.devEui),
          data: buildSeries(entry.history.items, activeMetric),
        }))
      : [
          {
            key: activeDevEui,
            label: labelFor(activeDevEui),
            data: buildSeries(items, activeMetric),
          },
        ];
  const hasData = chartSeries.some((entry) => entry.data.length > 0);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description={appName ?? appId}
        breadcrumbs={
          <Breadcrumbs
            items={[
              { label: 'Dashboard', to: '/dashboard' },
              { label: appName ?? appId },
            ]}
          />
        }
      />

      {devicesLoading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!devicesLoading && devicesError && (
        <Alert variant="error" onRetry={reloadDevices}>
          {devicesError}
        </Alert>
      )}

      {!devicesLoading && !devicesError && devices.length === 0 && (
        <EmptyState
          title="Nenhum device nesta aplicação"
          description="Provisione um device para começar a receber telemetria."
        />
      )}

      {!devicesLoading && !devicesError && devices.length > 0 && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:max-w-xl sm:grid-cols-2">
            <Select
              label="Device"
              name="dev_eui"
              value={activeDevEui}
              onChange={(event) => setSelectedDevEui(event.target.value)}
              options={[
                ...devices.map((device) => ({
                  value: device.dev_eui,
                  label: device.nickname ?? device.dev_eui,
                })),
                { value: ALL_DEVICES, label: 'Todos os devices' },
              ]}
            />
            <Select
              label="Métrica"
              name="metric"
              value={activeMetric}
              disabled={metrics.length === 0}
              onChange={(event) => setMetric(event.target.value)}
              options={metrics.map((key) => ({ value: key, label: key }))}
            />
          </div>

          <Card
            title={`Telemetria — ${activeMetric || 'sem métricas'}`}
            action={
              lastReadingTime ? (
                <span className="text-xs text-muted">
                  Última leitura: {formatDate(lastReadingTime)}
                </span>
              ) : undefined
            }
          >
            {historyLoading && (
              <div className="flex justify-center py-16">
                <Spinner size="lg" />
              </div>
            )}

            {!historyLoading && historyError && (
              <Alert variant="error" onRetry={reloadHistory}>
                {historyError}
              </Alert>
            )}

            {!historyLoading && !historyError && !hasData && (
              <EmptyState
                title="Sem telemetria"
                description="Nenhuma leitura disponível para o device selecionado."
              />
            )}

            {!historyLoading && !historyError && hasData && (
              <TelemetryLineChart series={chartSeries} />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
