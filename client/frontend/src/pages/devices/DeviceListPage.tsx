import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { tenantService, type TenantOutput } from '../../services/tenant';
import { loadApplicationsByTenant, type AppOption } from '../../services/app';
import type { ApplicationOutput } from '../../services/app';
import { deviceService, type DeviceOutput } from '../../services/device';
import { useAsyncData } from '../../hooks/useAsyncData';
import { getErrorMessage } from '../../services/api';
import { formatDate } from '../../utils/format';
import { PageHeader } from '../../components/layout/PageHeader';
import { Table, type Column } from '../../components/ui/Table';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { UuidDisplay } from '../../components/ui/UuidDisplay';
import { Edit, Plus, Trash } from '../../components/ui/icons';
import { DeviceNicknameModal } from './DeviceNicknameModal';

interface DeviceRow {
  device: DeviceOutput;
  app: ApplicationOutput;
  tenant: TenantOutput;
}

interface LoadResult {
  rows: DeviceRow[];
  apps: AppOption[];
}

async function loadDevices(): Promise<LoadResult> {
  const tenants = await tenantService.list();
  const appsByTenant = await loadApplicationsByTenant(tenants);

  const appEntries = tenants.flatMap((tenant) =>
    (appsByTenant[tenant.id] ?? []).map((app) => ({ app, tenant })),
  );

  const results = await Promise.allSettled(
    appEntries.map(async ({ app, tenant }) => {
      const devices = await deviceService.listByApp(app.id);
      return devices.map((device) => ({ device, app, tenant }));
    }),
  );

  const rows = results.flatMap((result) =>
    result.status === 'fulfilled' ? result.value : [],
  );

  const apps = appEntries.map(({ app, tenant }) => ({
    id: app.id,
    label: `${tenant.name} / ${app.name}`,
  }));

  return { rows, apps };
}

export default function DeviceListPage() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsyncData(loadDevices, []);
  const [deleting, setDeleting] = useState<DeviceRow | null>(null);
  const [editing, setEditing] = useState<DeviceRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const [query, setQuery] = useState('');

  const rows = data?.rows ?? [];
  const apps = data?.apps ?? [];
  const filtered = rows.filter((row) =>
    row.device.dev_eui.toLowerCase().includes(query.toLowerCase()),
  );

  async function handleDelete() {
    if (!deleting) return;
    setActionError('');
    setBusy(true);
    try {
      await deviceService.remove(deleting.device.id);
      setDeleting(null);
      reload();
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<DeviceRow>[] = [
    {
      key: 'dev_eui',
      header: 'DevEUI',
      render: (row) => (
        <span className="font-mono text-xs">{row.device.dev_eui}</span>
      ),
    },
    {
      key: 'id',
      header: 'Device ID',
      render: (row) => <UuidDisplay value={row.device.id} />,
    },
    {
      key: 'join_eui',
      header: 'JoinEUI',
      render: (row) => (
        <span className="font-mono text-xs">{row.device.join_eui}</span>
      ),
    },
    { key: 'app', header: 'Application', render: (row) => row.app.name },
    { key: 'tenant', header: 'Tenant', render: (row) => row.tenant.name },
    {
      key: 'nickname',
      header: 'Nickname',
      render: (row) => row.device.nickname ?? '—',
    },
    {
      key: 'created_at',
      header: 'Criado em',
      render: (row) => formatDate(row.device.created_at),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <div className="flex justify-end gap-1">
          <Button
            variant="ghost"
            aria-label={`Editar nickname ${row.device.dev_eui}`}
            onClick={() => setEditing(row)}
          >
            <Edit className="h-4 w-4 text-slate-500" />
          </Button>
          <Button
            variant="ghost"
            aria-label={`Excluir device ${row.device.dev_eui}`}
            onClick={() => setDeleting(row)}
          >
            <Trash className="h-4 w-4 text-red-500" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Devices"
        description="Todos os dispositivos da plataforma, por aplicação e tenant."
        actions={
          <Button
            onClick={() => navigate('/onboarding')}
            disabled={apps.length === 0}
          >
            <Plus className="h-4 w-4" />
            Novo Device
          </Button>
        }
      />

      {actionError && (
        <Alert variant="error" className="mb-4">
          {actionError}
        </Alert>
      )}

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!loading && error && (
        <Alert variant="error" onRetry={reload}>
          {error}
        </Alert>
      )}

      {!loading && !error && (
        <div className="space-y-4">
          <div className="max-w-xs">
            <Input
              label="Buscar por DevEUI"
              placeholder="Filtrar..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>

          {filtered.length === 0 ? (
            <EmptyState
              title="Nenhum device encontrado"
              description={
                apps.length === 0
                  ? 'Crie uma aplicação antes de provisionar dispositivos.'
                  : 'Provisione o primeiro dispositivo da plataforma.'
              }
              action={
                apps.length > 0 ? (
                  <Button onClick={() => navigate('/onboarding')}>
                    <Plus className="h-4 w-4" />
                    Novo Device
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <Table
              columns={columns}
              rows={filtered}
              rowKey={(row) => row.device.id}
            />
          )}
        </div>
      )}

      <ConfirmDialog
        open={deleting !== null}
        title="Excluir device"
        message={`Excluir o device "${deleting?.device.dev_eui}"? Esta ação é irreversível.`}
        confirmLabel="Excluir"
        loading={busy}
        onConfirm={handleDelete}
        onCancel={() => setDeleting(null)}
      />

      <DeviceNicknameModal
        open={editing !== null}
        device={editing?.device ?? null}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          reload();
        }}
      />
    </div>
  );
}
