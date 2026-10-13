import { useNavigate } from 'react-router-dom';
import { tenantService, type TenantOutput } from '../../services/tenant';
import { loadApplicationsByTenant, type ApplicationOutput } from '../../services/app';
import { useAsyncData } from '../../hooks/useAsyncData';
import { PageHeader } from '../../components/layout/PageHeader';
import { Table, type Column } from '../../components/ui/Table';
import { Button } from '../../components/ui/Button';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { ChevronRight } from '../../components/ui/icons';

interface AppRow {
  app: ApplicationOutput;
  tenant: TenantOutput;
}

async function loadApplications(): Promise<AppRow[]> {
  const tenants = await tenantService.list();
  const appsByTenant = await loadApplicationsByTenant(tenants);
  return tenants.flatMap((tenant) =>
    (appsByTenant[tenant.id] ?? []).map((app) => ({ app, tenant })),
  );
}

export default function DashboardSelectPage() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsyncData(loadApplications, []);

  const rows = data ?? [];

  const columns: Column<AppRow>[] = [
    { key: 'app', header: 'Application', render: (row) => row.app.name },
    { key: 'tenant', header: 'Tenant', render: (row) => row.tenant.name },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <Button
          variant="secondary"
          onClick={() =>
            navigate(`/dashboard/${row.app.id}`, {
              state: { appName: row.app.name },
            })
          }
        >
          Abrir dashboard
          <ChevronRight className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Escolha uma aplicação para visualizar a telemetria."
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

      {!loading && !error && (
        <>
          {rows.length === 0 ? (
            <EmptyState
              title="Nenhuma aplicação encontrada"
              description="Crie um tenant e uma aplicação antes de visualizar telemetria."
            />
          ) : (
            <Table
              columns={columns}
              rows={rows}
              rowKey={(row) => row.app.id}
            />
          )}
        </>
      )}
    </div>
  );
}
