import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import TenantListPage from './TenantListPage';

const server = setupServer(...handlers);
const base = 'http://localhost:8000/api/v1';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage() {
  return render(
    <MemoryRouter>
      <TenantListPage />
    </MemoryRouter>,
  );
}

describe('TenantListPage', () => {
  it('lists tenants returned by the API', async () => {
    renderPage();

    expect(await screen.findByText('Organização Alfa')).toBeInTheDocument();
    expect(screen.getByText('Organização Beta')).toBeInTheDocument();
  });

  it('shows tenant UUIDs with copy actions', async () => {
    const tenants = (await (await fetch(`${base}/tenant`)).json()) as {
      id: string;
    }[];

    renderPage();

    await screen.findByText('Organização Alfa');
    expect(screen.getByText(tenants[0].id)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: `Copiar UUID ${tenants[0].id}` }),
    ).toBeInTheDocument();
  });

  it('creates a tenant through the modal', async () => {
    renderPage();
    await screen.findByText('Organização Alfa');

    await userEvent.click(screen.getByRole('button', { name: /novo tenant/i }));

    await userEvent.type(screen.getByLabelText('Nome'), 'Tenant Gama');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByText('Tenant Gama')).toBeInTheDocument();
  });

  it('shows an empty state when there are no tenants', async () => {
    server.use(http.get('*/api/v1/tenant', () => HttpResponse.json([])));

    renderPage();

    expect(
      await screen.findByText('Nenhum tenant encontrado'),
    ).toBeInTheDocument();
  });

  it('shows an error with retry when loading fails', async () => {
    server.use(
      http.get('*/api/v1/tenant', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );

    renderPage();

    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument());
    expect(
      screen.getByRole('button', { name: 'Tentar novamente' }),
    ).toBeInTheDocument();
  });
});
