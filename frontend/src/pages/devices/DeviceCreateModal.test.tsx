import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import { DeviceCreateModal, type AppOption } from './DeviceCreateModal';
import type { DeviceOutput } from '../../services/device';

const server = setupServer(...handlers);
const base = 'http://localhost:8000/api/v1';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function firstApp(): Promise<AppOption> {
  const tenants = (await (await fetch(`${base}/tenant`)).json()) as {
    id: string;
    name: string;
  }[];
  const apps = (await (
    await fetch(`${base}/tenant/${tenants[0].id}/applications`)
  ).json()) as { id: string; name: string }[];
  return { id: apps[0].id, label: apps[0].name };
}

const VALID_EUI = '1122334455667788';
const VALID_KEY = '00112233445566778899aabbccddeeff';

function renderModal(
  app: AppOption,
  onCreated = vi.fn<(d: DeviceOutput) => void>(),
  onClose = vi.fn(),
) {
  render(
    <DeviceCreateModal
      open
      apps={[app]}
      onClose={onClose}
      onCreated={onCreated}
    />,
  );
  return { onCreated, onClose };
}

describe('DeviceCreateModal', () => {
  it('loads device profiles when an app is selected', async () => {
    const app = await firstApp();
    renderModal(app);

    await userEvent.selectOptions(screen.getByLabelText('Aplicação'), app.id);

    expect(
      await screen.findByRole('option', { name: 'Perfil Teste' }),
    ).toBeInTheDocument();
  });

  it('shows an error alert when profile fetch fails', async () => {
    const app = await firstApp();
    server.use(
      http.get('*/api/v1/device-profile/', () =>
        HttpResponse.json({ detail: 'grpc down' }, { status: 502 }),
      ),
    );
    renderModal(app);

    await userEvent.selectOptions(screen.getByLabelText('Aplicação'), app.id);

    expect(await screen.findByText('grpc down')).toBeInTheDocument();
  });

  it('shows Zod validation errors on submit with invalid fields', async () => {
    const app = await firstApp();
    renderModal(app);

    await userEvent.click(screen.getByRole('button', { name: 'Criar' }));

    const errors = await screen.findAllByText('Deve ter 16 caracteres hexadecimais');
    expect(errors.length).toBeGreaterThanOrEqual(1);
  });

  it('calls onCreated and closes modal on successful submit', async () => {
    const app = await firstApp();
    const { onCreated, onClose } = renderModal(app);

    await userEvent.selectOptions(screen.getByLabelText('Aplicação'), app.id);
    await screen.findByRole('option', { name: 'Perfil Teste' });

    await userEvent.type(screen.getByLabelText('DevEUI'), VALID_EUI);
    await userEvent.type(screen.getByLabelText('JoinEUI'), VALID_EUI);
    await userEvent.type(screen.getByLabelText('AppKey'), VALID_KEY);
    await userEvent.click(screen.getByRole('button', { name: 'Criar' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledOnce());
    expect(onClose).toHaveBeenCalledOnce();
  });
});
