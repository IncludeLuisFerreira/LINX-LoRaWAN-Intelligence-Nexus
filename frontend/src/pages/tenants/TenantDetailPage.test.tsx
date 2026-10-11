import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import TenantDetailPage from './TenantDetailPage';

const server = setupServer(...handlers);
const base = 'http://localhost:8000/api/v1';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function firstTenant(): Promise<{ id: string; name: string }> {
  const res = await fetch(`${base}/tenant`);
  const tenants = (await res.json()) as { id: string; name: string }[];
  return tenants[0];
}

function renderDetail(tenantId: string) {
  return render(
    <MemoryRouter initialEntries={[`/tenants/${tenantId}`]}>
      <Routes>
        <Route path="/tenants/:tenantId" element={<TenantDetailPage />} />
        <Route path="/tenants" element={<div>TENANTS INDEX</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('TenantDetailPage', () => {
  it('renders the tenant and its applications on deep-link', async () => {
    const tenant = await firstTenant();

    renderDetail(tenant.id);

    expect(await screen.findByRole("heading", { name: tenant.name })).toBeInTheDocument();
    expect(screen.getByText('App Sensores')).toBeInTheDocument();
  });

  it('creates an application under the tenant', async () => {
    const tenant = await firstTenant();
    renderDetail(tenant.id);
    await screen.findByRole("heading", { name: tenant.name });

    await userEvent.click(
      screen.getByRole('button', { name: /nova application/i }),
    );
    await userEvent.type(screen.getByLabelText('Nome'), 'App Nova');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByText('App Nova')).toBeInTheDocument();
  });

  it('deletes the tenant and navigates back to the list', async () => {
    const tenant = await firstTenant();
    renderDetail(tenant.id);
    await screen.findByRole("heading", { name: tenant.name });

    await userEvent.click(screen.getByRole('tab', { name: 'Configurações' }));
    await userEvent.click(
      screen.getByRole('button', { name: /excluir tenant/i }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Excluir' }));

    expect(await screen.findByText('TENANTS INDEX')).toBeInTheDocument();
  });
});
