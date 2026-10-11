import { useState } from 'react';
import { Link } from 'react-router-dom';
import { tenantService, type TenantOutput } from '../../services/tenant';
import { loadApplicationsByTenant } from '../../services/app';
import { useAsyncData } from '../../hooks/useAsyncData';
import { getErrorMessage } from '../../services/api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Edit, Plus, Trash } from '../../components/ui/icons';
import {
  TenantFormModal,
  type TenantFormData,
} from './TenantFormModal';

type LoadResult = {
  tenants: TenantOutput[];
  appsByTenant: Record<string, unknown[]>;
};

async function loadTenants(): Promise<LoadResult> {
  const tenants = await tenantService.list();
  const appsByTenant = await loadApplicationsByTenant(tenants);
  return { tenants, appsByTenant };
}

export default function TenantListPage() {
  const { data, error, loading, reload } = useAsyncData(loadTenants, []);
  const [editing, setEditing] = useState<TenantOutput | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<TenantOutput | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');

  const tenants = data?.tenants ?? [];

  async function handleSubmit(values: TenantFormData) {
    setFormError('');
    setBusy(true);
    try {
      if (editing) {
        await tenantService.update(editing.id, values);
      } else {
        await tenantService.create(values);
      }
      setEditing(null);
      setCreating(false);
      reload();
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    setBusy(true);
    try {
      await tenantService.remove(deleting.id);
      setDeleting(null);
      reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Tenants"
        description="Gerencie as organizações da plataforma."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            Novo Tenant
          </Button>
        }
      />

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

      {!loading && !error && tenants.length === 0 && (
        <EmptyState
          title="Nenhum tenant encontrado"
          description="Crie o primeiro tenant para começar a organizar sua arquitetura."
          action={
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              Novo Tenant
            </Button>
          }
        />
      )}

      {!loading && !error && tenants.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tenants.map((tenant) => (
            <Card key={tenant.id}>
              <div className="flex items-start justify-between gap-2">
                <Link
                  to={`/tenants/${tenant.id}`}
                  className="text-base font-semibold text-slate-800 transition-colors hover:text-primary-600"
                >
                  {tenant.name}
                </Link>
                <Badge color="blue">
                  {data?.appsByTenant[tenant.id]?.length ?? 0} apps
                </Badge>
              </div>
              <p className="mt-1 min-h-[1.25rem] text-sm text-muted">
                {tenant.description || 'Sem descrição'}
              </p>
              <div className="mt-4 flex justify-end gap-1">
                <Button
                  variant="ghost"
                  aria-label={`Editar ${tenant.name}`}
                  onClick={() => setEditing(tenant)}
                >
                  <Edit className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  aria-label={`Excluir ${tenant.name}`}
                  onClick={() => setDeleting(tenant)}
                >
                  <Trash className="h-4 w-4 text-red-500" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <TenantFormModal
        open={creating || editing !== null}
        title={editing ? 'Editar Tenant' : 'Novo Tenant'}
        initial={
          editing
            ? { name: editing.name, description: editing.description }
            : undefined
        }
        error={formError}
        onClose={() => {
          setCreating(false);
          setEditing(null);
          setFormError('');
        }}
        onSubmit={handleSubmit}
      />

      <ConfirmDialog
        open={deleting !== null}
        title="Excluir tenant"
        message={`Excluir "${deleting?.name}" e todas as suas aplicações? Esta ação é irreversível.`}
        confirmLabel="Excluir"
        loading={busy}
        onConfirm={handleDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
