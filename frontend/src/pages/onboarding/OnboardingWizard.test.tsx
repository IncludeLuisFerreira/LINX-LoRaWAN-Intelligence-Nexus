import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import OnboardingWizard from './OnboardingWizard';
import type { Tr005Data } from '../../utils/tr005';

vi.mock('../../components/QrScanner', () => ({
  QrScanner: ({
    onDecoded,
    onClose,
  }: {
    onDecoded: (data: Tr005Data) => void;
    onClose: () => void;
  }) => (
    <div data-testid="qr-scanner-stub">
      <button
        type="button"
        onClick={() =>
          onDecoded({
            schemaId: 'D0',
            joinEUI: '1122334455667788',
            devEUI: 'aabbccddeeff0011',
            profileId: 'AABB1122',
          })
        }
      >
        simular-decode
      </button>
      <button type="button" onClick={onClose}>
        cancelar-scanner
      </button>
    </div>
  ),
}));

const server = setupServer(...handlers);
const base = 'http://localhost:8000/api/v1';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function firstAppId(): Promise<string> {
  const tenants = (await (await fetch(`${base}/tenant`)).json()) as {
    id: string;
  }[];
  const apps = (await (
    await fetch(`${base}/tenant/${tenants[0].id}/applications`)
  ).json()) as { id: string }[];
  return apps[0].id;
}

function renderWizard(path = '/onboarding') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/onboarding" element={<OnboardingWizard />} />
        <Route path="/devices" element={<div>devices-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function decodeToStep2() {
  renderWizard();
  await userEvent.click(
    await screen.findByRole('button', { name: 'simular-decode' }),
  );
  await screen.findByLabelText('DevEUI');
}

async function goToStep3() {
  await userEvent.click(screen.getByRole('button', { name: 'Continuar' }));
  await screen.findByText(/Passo 3 de 3/i);
}

describe('OnboardingWizard', () => {
  it('starts at step 1 with the QR scanner', async () => {
    renderWizard();
    expect(await screen.findByTestId('qr-scanner-stub')).toBeInTheDocument();
    expect(screen.getByText(/Passo 1 de 3/i)).toBeInTheDocument();
  });

  it('cancelling the scanner redirects to the devices page', async () => {
    renderWizard();
    await userEvent.click(
      await screen.findByRole('button', { name: 'cancelar-scanner' }),
    );
    expect(await screen.findByText('devices-page')).toBeInTheDocument();
  });

  it('prefills step 2 with QR data and a generated AppKey', async () => {
    await decodeToStep2();

    expect(screen.getByLabelText('DevEUI')).toHaveValue('aabbccddeeff0011');
    expect(screen.getByLabelText('JoinEUI')).toHaveValue('1122334455667788');
    const appKey = screen.getByLabelText<HTMLInputElement>('AppKey');
    expect(appKey.value).toMatch(/^[0-9A-F]{32}$/);
    expect(screen.getByLabelText('ProfileID (QR Code)')).toHaveValue(
      'AABB1122',
    );
  });

  it('blocks step 2 advance when a field is invalid', async () => {
    await decodeToStep2();

    const devEui = screen.getByLabelText('DevEUI');
    await userEvent.clear(devEui);
    await userEvent.type(devEui, 'ZZ');
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }));

    expect(
      await screen.findByText('Deve ter 16 caracteres hexadecimais'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Passo 3 de 3/i)).not.toBeInTheDocument();
  });

  it('blocks step 2 advance when the AppKey is edited to an invalid value', async () => {
    await decodeToStep2();

    const appKey = screen.getByLabelText('AppKey');
    await userEvent.clear(appKey);
    await userEvent.type(appKey, 'abc');
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }));

    expect(
      await screen.findByText('Deve ter 32 caracteres hexadecimais'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Passo 3 de 3/i)).not.toBeInTheDocument();
  });

  it('loads apps and device profiles on step 3', async () => {
    const appId = await firstAppId();
    await decodeToStep2();
    await goToStep3();

    await userEvent.selectOptions(
      await screen.findByLabelText('Aplicação'),
      appId,
    );

    expect(
      await screen.findByRole('option', { name: 'Perfil Teste' }),
    ).toBeInTheDocument();
  });

  it('preselects the device profile matching the QR ProfileID', async () => {
    const appId = await firstAppId();
    server.use(
      http.get('*/api/v1/device-profile/', () =>
        HttpResponse.json([
          { id: 'uuid-other', name: 'Outro' },
          { id: 'uuid-match', name: 'AABB1122' },
        ]),
      ),
    );

    await decodeToStep2();
    await goToStep3();
    await userEvent.selectOptions(
      await screen.findByLabelText('Aplicação'),
      appId,
    );

    await screen.findByRole('option', { name: 'AABB1122' });
    expect(screen.getByLabelText('Device Profile')).toHaveValue('uuid-match');
    expect(
      screen.queryByText(/não corresponde a nenhum perfil/i),
    ).not.toBeInTheDocument();
  });

  it('warns when the QR ProfileID does not match any profile (fallback)', async () => {
    const appId = await firstAppId();

    await decodeToStep2();
    await goToStep3();
    await userEvent.selectOptions(
      await screen.findByLabelText('Aplicação'),
      appId,
    );

    expect(
      await screen.findByText(/não corresponde a nenhum perfil/i),
    ).toBeInTheDocument();
  });

  it('submits the device with the real contract and redirects', async () => {
    const appId = await firstAppId();
    await decodeToStep2();
    await goToStep3();

    await userEvent.selectOptions(
      await screen.findByLabelText('Aplicação'),
      appId,
    );
    await screen.findByRole('option', { name: 'Perfil Teste' });

    await userEvent.click(
      screen.getByRole('button', { name: 'Cadastrar device' }),
    );

    expect(await screen.findByText('devices-page')).toBeInTheDocument();

    const devices = (await (
      await fetch(`${base}/devices?app_id=${appId}`)
    ).json()) as { dev_eui: string }[];
    expect(
      devices.some((device) => device.dev_eui === 'aabbccddeeff0011'),
    ).toBe(true);
  });

  it('shows an error alert and stays on step 3 when submit fails', async () => {
    const appId = await firstAppId();
    server.use(
      http.post('*/api/v1/devices', () =>
        HttpResponse.json(
          { detail: 'Device already exists!' },
          { status: 409 },
        ),
      ),
    );

    await decodeToStep2();
    await goToStep3();
    await userEvent.selectOptions(
      await screen.findByLabelText('Aplicação'),
      appId,
    );
    await screen.findByRole('option', { name: 'Perfil Teste' });

    await userEvent.click(
      screen.getByRole('button', { name: 'Cadastrar device' }),
    );

    expect(
      await screen.findByText('Device already exists!'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Passo 3 de 3/i)).toBeInTheDocument();
  });

  it('locks and preselects the application from the ?app= query', async () => {
    const appId = await firstAppId();
    renderWizard(`/onboarding?app=${appId}`);

    await userEvent.click(
      await screen.findByRole('button', { name: 'simular-decode' }),
    );
    const devEui = screen.getByLabelText('DevEUI');
    await userEvent.clear(devEui);
    await userEvent.type(devEui, 'aabbccddeeff7777');
    await goToStep3();

    expect(screen.getByLabelText<HTMLInputElement>('Aplicação').value).toMatch(
      /App Sensores/,
    );
    expect(
      await screen.findByRole('option', { name: 'Perfil Teste' }),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: 'Cadastrar device' }),
    );
    expect(await screen.findByText('devices-page')).toBeInTheDocument();
  });

  it('keeps step 2 data when going back from step 3', async () => {
    await decodeToStep2();
    const devEui = screen.getByLabelText('DevEUI');
    await userEvent.clear(devEui);
    await userEvent.type(devEui, 'aabbccddeeff9999');
    await goToStep3();

    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }));

    await waitFor(() =>
      expect(screen.getByLabelText('DevEUI')).toHaveValue('aabbccddeeff9999'),
    );
  });

  it('shows an empty state and disables submit when the app has no device profiles', async () => {
    const appId = await firstAppId();
    server.use(
      http.get('*/api/v1/device-profile/', () => HttpResponse.json([])),
    );

    await decodeToStep2();
    await goToStep3();
    await userEvent.selectOptions(
      await screen.findByLabelText('Aplicação'),
      appId,
    );

    expect(
      await screen.findByText(/Nenhum device profile nesta aplicação/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Cadastrar device' }),
    ).toBeDisabled();
  });

  it('shows the profile fetch error and disables submit', async () => {
    const appId = await firstAppId();
    server.use(
      http.get('*/api/v1/device-profile/', () =>
        HttpResponse.json({ detail: 'Falha ao carregar perfis' }, { status: 500 }),
      ),
    );

    await decodeToStep2();
    await goToStep3();
    await userEvent.selectOptions(
      await screen.findByLabelText('Aplicação'),
      appId,
    );

    expect(
      await screen.findByText('Falha ao carregar perfis'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Cadastrar device' }),
    ).toBeDisabled();
  });

  it('warns when the ?app= link does not resolve to a known application', async () => {
    renderWizard('/onboarding?app=00000000-0000-0000-0000-000000000000');

    await userEvent.click(
      await screen.findByRole('button', { name: 'simular-decode' }),
    );
    await screen.findByLabelText('DevEUI');
    await goToStep3();

    expect(
      await screen.findByText(/A aplicação informada no link não foi encontrada/i),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText('Aplicação')).toBeInTheDocument();
  });
});
