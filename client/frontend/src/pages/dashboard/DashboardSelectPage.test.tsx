import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import DashboardSelectPage from './DashboardSelectPage';

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route path="/dashboard" element={<DashboardSelectPage />} />
        <Route path="/dashboard/:appId" element={<div>app-dashboard</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('DashboardSelectPage', () => {
  it('lists applications and navigates to the chosen dashboard', async () => {
    renderPage();

    expect(await screen.findByText('App Sensores')).toBeInTheDocument();

    await userEvent.click(
      screen.getAllByRole('button', { name: /abrir dashboard/i })[0],
    );

    expect(await screen.findByText('app-dashboard')).toBeInTheDocument();
  });
});
