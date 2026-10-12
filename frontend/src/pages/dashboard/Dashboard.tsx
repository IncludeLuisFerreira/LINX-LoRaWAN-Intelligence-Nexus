import { useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { deviceService } from '../../services/device';
import {
  telemetryService,
  numericMetrics,
  buildSeries,
  type TelemetryHistory,
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

const EMPTY_HISTORY: TelemetryHistory = { items: [], next_cursor: null };

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

  const activeDevEui = devices.some(
    (device) => device.dev_eui === selectedDevEui,
  )
    ? selectedDevEui
    : (devices[0]?.dev_eui ?? '');

  const {
    data: history,
    error: historyError,
    loading: historyLoading,
    reload: reloadHistory,
  } = useAsyncData(
    () =>
      activeDevEui
        ? telemetryService.history(activeDevEui)
        : Promise.resolve(EMPTY_HISTORY),
    [appId, activeDevEui],
  );

  const items = history?.items ?? [];
  const metrics = numericMetrics(items);
  const activeMetric = metrics.includes(metric) ? metric : (metrics[0] ?? '');
  const series = activeMetric ? buildSeries(items, activeMetric) : [];

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
              options={devices.map((device) => ({
                value: device.dev_eui,
                label: device.dev_eui,
              }))}
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
              items.length > 0 ? (
                <span className="text-xs text-muted">
                  Última leitura: {formatDate(items[0].time)}
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

            {!historyLoading && !historyError && series.length === 0 && (
              <EmptyState
                title="Sem telemetria"
                description="Nenhuma leitura disponível para o device selecionado."
              />
            )}

            {!historyLoading && !historyError && series.length > 0 && (
              <TelemetryLineChart data={series} label={activeMetric} />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
