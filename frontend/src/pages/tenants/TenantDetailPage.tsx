import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { tenantService } from '../../services/tenant';
import {
  applicationService,
  type ApplicationOutput,
} from '../../services/app';
import type { TenantOutput } from '../../services/tenant';
import { useAsyncData } from '../../hooks/useAsyncData';
import { getErrorMessage } from '../../services/api';
import { formatDate } from '../../utils/format';
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
import { Plus, Trash, Edit } from '../../components/ui/icons';
import {
  TenantFormModal,
  type TenantFormData,
} from './TenantFormModal';
import {
  ApplicationFormModal,
  type ApplicationFormData,
} from '../applications/ApplicationFormModal';

type LoadResult = { tenant: TenantOutput; apps: ApplicationOutput[] };

async function loadTenant(tenantId: string): Promise<LoadResult> {
  const [tenant, apps] = await Promise.all([
    tenantService.get(tenantId),
    applicationService.listByTenant(tenantId),
  ]);
  return { tenant, apps };
}

export default function TenantDetailPage() {
  const { tenantId = '' } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsyncData(
    () => loadTenant(tenantId),
    [tenantId],
  );

  const [tab, setTab] = useState('applications');
  const [creatingApp, setCreatingApp] = useState(false);
  const [editingTenant, setEditingTenant] = useState(false);
  const [deletingTenant, setDeletingTenant] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');

  const tenant = data?.tenant;
  const apps = data?.apps ?? [];

  async function createApp(values: ApplicationFormData) {
    setFormError('');
    setBusy(true);
    try {
      await applicationService.create(tenantId, values);
      setCreatingApp(false);
      reload();
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function updateTenant(values: TenantFormData) {
    setFormError('');
    setBusy(true);
    try {
      await tenantService.update(tenantId, values);
      setEditingTenant(false);
      reload();
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteTenant() {
    setBusy(true);
    try {
      await tenantService.remove(tenantId);
      navigate('/tenants');
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

  if (error || !tenant) {
    return <Alert variant="error" onRetry={reload}>{error || 'Tenant não encontrado'}</Alert>;
  }

  const columns: Column<ApplicationOutput>[] = [
    {
      key: 'name',
      header: 'Nome',
      render: (app) => (
        <Link
          to={`/tenants/${tenantId}/applications/${app.id}`}
          className="font-medium text-primary-600 hover:underline"
        >
          {app.name}
        </Link>
      ),
    },
    {
      key: 'description',
      header: 'Descrição',
      render: (app) => app.description || '—',
    },
    {
      key: 'created_at',
      header: 'Criada em',
      render: (app) => formatDate(app.created_at),
    },
  ];

  return (
    <div>
      <PageHeader
        title={tenant.name}
        description={tenant.description || undefined}
        breadcrumbs={
          <Breadcrumbs
            items={[
              { label: 'Tenants', to: '/tenants' },
              { label: tenant.name },
            ]}
          />
        }
        actions={
          <Button variant="secondary" onClick={() => setEditingTenant(true)}>
            <Edit className="h-4 w-4" />
            Editar
          </Button>
        }
      />

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          {
            id: 'applications',
            label: 'Applications',
            content: (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <Button onClick={() => setCreatingApp(true)}>
                    <Plus className="h-4 w-4" />
                    Nova Application
                  </Button>
                </div>
                {apps.length === 0 ? (
                  <EmptyState
                    title="Nenhuma aplicação"
                    description="Crie a primeira aplicação deste tenant."
                    action={
                      <Button onClick={() => setCreatingApp(true)}>
                        <Plus className="h-4 w-4" />
                        Nova Application
                      </Button>
                    }
                  />
                ) : (
                  <Table
                    columns={columns}
                    rows={apps}
                    rowKey={(app) => app.id}
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
                  Excluir o tenant remove todas as suas aplicações e
                  dispositivos.
                </p>
                <Button
                  variant="danger"
                  className="mt-4"
                  onClick={() => setDeletingTenant(true)}
                >
                  <Trash className="h-4 w-4" />
                  Excluir tenant
                </Button>
              </Card>
            ),
          },
        ]}
      />

      <ApplicationFormModal
        open={creatingApp}
        title="Nova Application"
        error={formError}
        onClose={() => {
          setCreatingApp(false);
          setFormError('');
        }}
        onSubmit={createApp}
      />

      <TenantFormModal
        open={editingTenant}
        title="Editar Tenant"
        initial={{ name: tenant.name, description: tenant.description }}
        error={formError}
        onClose={() => {
          setEditingTenant(false);
          setFormError('');
        }}
        onSubmit={updateTenant}
      />

      <ConfirmDialog
        open={deletingTenant}
        title="Excluir tenant"
        message={`Excluir "${tenant.name}" e todas as suas aplicações? Esta ação é irreversível.`}
        confirmLabel="Excluir"
        loading={busy}
        onConfirm={deleteTenant}
        onCancel={() => setDeletingTenant(false)}
      />
    </div>
  );
}
