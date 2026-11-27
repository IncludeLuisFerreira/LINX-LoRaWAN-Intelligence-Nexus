import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import Rules from './Rules';

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage() {
  return render(
    <MemoryRouter>
      <Rules />
    </MemoryRouter>,
  );
}

async function fillRule(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Campo do sensor'), 'temperatura');
  await user.selectOptions(screen.getByLabelText('Operador'), '>');
  const threshold = screen.getByLabelText('Limite');
  await user.clear(threshold);
  await user.type(threshold, '40');
  await user.selectOptions(screen.getByLabelText('Ação'), 'downlink');
}

describe('Rules', () => {
  it('creates a rule with the four required fields and lists it', async () => {
    const user = userEvent.setup();
    const stored: unknown[] = [];
    let created: unknown;
    server.use(
      http.get('*/api/v1/rules', () => HttpResponse.json(stored)),
      http.post('*/api/v1/rules', async ({ request }) => {
        created = await request.json();
        const rule = { id: 'rule-1', ...(created as object) };
        stored.push(rule);
        return HttpResponse.json(rule, { status: 201 });
      }),
    );

    renderPage();

    expect(
      await screen.findByText('Nenhuma regra cadastrada'),
    ).toBeInTheDocument();
    await fillRule(user);
    await user.click(screen.getByRole('button', { name: 'Criar regra' }));

    expect(await screen.findByText('temperatura')).toBeInTheDocument();
    expect(screen.getByText('40')).toBeInTheDocument();
    expect(screen.getByText('downlink')).toBeInTheDocument();
    expect(created).toEqual({
      sensor_field: 'temperatura',
      operator: '>',
      threshold: 40,
      action_type: 'downlink',
    });
  });

  it('offers the required operator and action options', () => {
    renderPage();

    expect(screen.getByLabelText('Operador')).toHaveTextContent('==');
    expect(screen.getByLabelText('Operador')).toHaveTextContent('!=');
    expect(screen.getByLabelText('Ação')).toHaveTextContent('Telegram');
    expect(screen.getByLabelText('Ação')).toHaveTextContent('E-mail');
  });

  it('does not submit when sensor_field is empty', async () => {
    const user = userEvent.setup();
    const post = vi.fn();
    server.use(
      http.get('*/api/v1/rules', () => HttpResponse.json([])),
      http.post('*/api/v1/rules', async ({ request }) => {
        post(await request.json());
        return HttpResponse.json({}, { status: 201 });
      }),
    );

    renderPage();
    await user.click(screen.getByRole('button', { name: 'Criar regra' }));

    expect(
      await screen.findByText('Informe o campo do sensor'),
    ).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it('shows an error returned by the API', async () => {
    const user = userEvent.setup();
    server.use(
      http.get('*/api/v1/rules', () => HttpResponse.json([])),
      http.post('*/api/v1/rules', () =>
        HttpResponse.json({ detail: 'backend indisponível' }, { status: 500 }),
      ),
    );

    renderPage();
    await fillRule(user);
    await user.click(screen.getByRole('button', { name: 'Criar regra' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'backend indisponível',
    );
  });

  it('retries the listing after a GET failure', async () => {
    const user = userEvent.setup();
    let calls = 0;
    server.use(
      http.get('*/api/v1/rules', () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ detail: 'falha ao listar' }, { status: 500 })
          : HttpResponse.json([]);
      }),
    );

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'falha ao listar',
    );
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }));

    expect(
      await screen.findByText('Nenhuma regra cadastrada'),
    ).toBeInTheDocument();
  });
});
