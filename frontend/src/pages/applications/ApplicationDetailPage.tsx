import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { tenantService } from '../../services/tenant';
import { applicationService, type ApplicationOutput } from '../../services/app';
import { deviceService, type DeviceOutput } from '../../services/device';
import type { TenantOutput } from '../../services/tenant';
import { useAsyncData } from '../../hooks/useAsyncData';
import { getErrorMessage } from '../../services/api';
import { formatDate } from '../../utils/format';
import { cleanOptionalDescription } from '../../utils/form';
import { PageHeader } from '../../components/layout/PageHeader';
import { Breadcrumbs } from '../../components/ui/Breadcrumbs';
import { Tabs } from '../../components/ui/Tabs';
import { Card } from '../../components/ui/Card';
import { Table, type Column } from '../../components/ui/Table';
import { Button } from '../../components/ui/Button';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Edit, Plus, Trash } from '../../components/ui/icons';
import {
  ApplicationFormModal,
  type ApplicationFormData,
} from './ApplicationFormModal';

type LoadResult = {
  tenant: TenantOutput;
  app: ApplicationOutput;
  devices: DeviceOutput[];
};

async function loadApplication(
  tenantId: string,
  appId: string,
): Promise<LoadResult> {
  const [tenant, app, devices] = await Promise.all([
    tenantService.get(tenantId),
    applicationService.get(tenantId, appId),
    deviceService.listByApp(appId),
  ]);
  return { tenant, app, devices };
}

export default function ApplicationDetailPage() {
  const { tenantId = '', appId = '' } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsyncData(
    () => loadApplication(tenantId, appId),
    [tenantId, appId],
  );

  const [tab, setTab] = useState('devices');
  const [editingApp, setEditingApp] = useState(false);
  const [deletingDevice, setDeletingDevice] = useState<DeviceOutput | null>(
    null,
  );
  const [deletingApp, setDeletingApp] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');
  const [actionError, setActionError] = useState('');

  const tenant = data?.tenant;
  const app = data?.app;
  const devices = data?.devices ?? [];

  async function updateApp(values: ApplicationFormData) {
    setFormError('');
    setBusy(true);
    try {
      await applicationService.update(
        tenantId,
        appId,
        cleanOptionalDescription(values),
      );
      setEditingApp(false);
      reload();
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteDevice() {
    if (!deletingDevice) return;
    setActionError('');
    setBusy(true);
    try {
      await deviceService.remove(deletingDevice.id);
      setDeletingDevice(null);
      reload();
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteApp() {
    setActionError('');
    setBusy(true);
    try {
      await applicationService.remove(tenantId, appId);
      navigate(`/tenants/${tenantId}`);
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !app || !tenant) {
    return (
      <Alert variant="error" onRetry={reload}>
        {error || 'Application não encontrada'}
      </Alert>
    );
  }

  const columns: Column<DeviceOutput>[] = [
    {
      key: 'dev_eui',
      header: 'DevEUI',
      render: (device) => (
        <span className="font-mono text-xs">{device.dev_eui}</span>
      ),
    },
    {
      key: 'join_eui',
      header: 'JoinEUI',
      render: (device) => (
        <span className="font-mono text-xs">{device.join_eui}</span>
      ),
    },
    {
      key: 'created_at',
      header: 'Criado em',
      render: (device) => formatDate(device.created_at),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (device) => (
        <Button
          variant="ghost"
          aria-label={`Excluir device ${device.dev_eui}`}
          onClick={() => setDeletingDevice(device)}
        >
          <Trash className="h-4 w-4 text-red-500" />
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title={app.name}
        description={app.description || undefined}
        breadcrumbs={
          <Breadcrumbs
            items={[
              { label: 'Tenants', to: '/tenants' },
              { label: tenant.name, to: `/tenants/${tenantId}` },
              { label: app.name },
            ]}
          />
        }
        actions={
          <Button variant="secondary" onClick={() => setEditingApp(true)}>
            <Edit className="h-4 w-4" />
            Editar
          </Button>
        }
      />

      {actionError && (
        <Alert variant="error" className="mb-4">
          {actionError}
        </Alert>
      )}

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          {
            id: 'devices',
            label: 'Devices',
            content: (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <Button onClick={() => navigate(`/onboarding?app=${appId}`)}>
                    <Plus className="h-4 w-4" />
                    Novo Device
                  </Button>
                </div>
                {devices.length === 0 ? (
                  <EmptyState
                    title="Nenhum device"
                    description="Provisione o primeiro dispositivo desta aplicação."
                    action={
                      <Button
                        onClick={() => navigate(`/onboarding?app=${appId}`)}
                      >
                        <Plus className="h-4 w-4" />
                        Novo Device
                      </Button>
                    }
                  />
                ) : (
                  <Table
                    columns={columns}
                    rows={devices}
                    rowKey={(device) => device.id}
                  />
                )}
              </div>
            ),
          },
          {
            id: 'settings',
            label: 'Configurações',
            content: (
              <Card title="Zona de perigo">
                <p className="text-sm text-muted">
                  Excluir a application remove todos os seus dispositivos.
                </p>
                <Button
                  variant="danger"
                  className="mt-4"
                  onClick={() => setDeletingApp(true)}
                >
                  <Trash className="h-4 w-4" />
                  Excluir application
                </Button>
              </Card>
            ),
          },
        ]}
      />

      <ApplicationFormModal
        open={editingApp}
        title="Editar Application"
        initial={{ name: app.name, description: app.description }}
        error={formError}
        onClose={() => {
          setEditingApp(false);
          setFormError('');
        }}
        onSubmit={updateApp}
      />

      <ConfirmDialog
        open={deletingDevice !== null}
        title="Excluir device"
        message={`Excluir o device "${deletingDevice?.dev_eui}"? Esta ação é irreversível.`}
        confirmLabel="Excluir"
        loading={busy}
        onConfirm={deleteDevice}
        onCancel={() => setDeletingDevice(null)}
      />

      <ConfirmDialog
        open={deletingApp}
        title="Excluir application"
        message={`Excluir "${app.name}" e todos os seus dispositivos? Esta ação é irreversível.`}
        confirmLabel="Excluir"
        loading={busy}
        onConfirm={deleteApp}
        onCancel={() => setDeletingApp(false)}
      />
    </div>
  );
}
