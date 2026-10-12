import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import ApplicationDetailPage from './ApplicationDetailPage';

const server = setupServer(...handlers);
const base = 'http://localhost:8000/api/v1';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function firstTenantAndApp(): Promise<{
  tenantId: string;
  appId: string;
  appName: string;
}> {
  const tenants = (await (await fetch(`${base}/tenant`)).json()) as {
    id: string;
    name: string;
  }[];
  const tenantId = tenants[0].id;
  const apps = (await (
    await fetch(`${base}/tenant/${tenantId}/applications`)
  ).json()) as { id: string; name: string }[];
  return { tenantId, appId: apps[0].id, appName: apps[0].name };
}

function renderDetail(tenantId: string, appId: string) {
  return render(
    <MemoryRouter
      initialEntries={[`/tenants/${tenantId}/applications/${appId}`]}
    >
      <Routes>
        <Route
          path="/tenants/:tenantId/applications/:appId"
          element={<ApplicationDetailPage />}
        />
        <Route path="/onboarding" element={<div>wizard-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ApplicationDetailPage', () => {
  it('renders the app and shows an empty device state', async () => {
    const { tenantId, appId, appName } = await firstTenantAndApp();

    renderDetail(tenantId, appId);

    expect(
      await screen.findByRole('heading', { name: appName }),
    ).toBeInTheDocument();
    expect(screen.getByText('Nenhum device')).toBeInTheDocument();
  });

  it('navigates to the onboarding wizard scoped to the app', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    renderDetail(tenantId, appId);
    await screen.findByText('Nenhum device');

    await userEvent.click(
      screen.getAllByRole('button', { name: /novo device/i })[0],
    );

    expect(await screen.findByText('wizard-page')).toBeInTheDocument();
  });
});
