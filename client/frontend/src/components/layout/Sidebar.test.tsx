import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from './Sidebar';

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar isOpen onClose={() => {}} />
    </MemoryRouter>,
  );
}

describe('Sidebar', () => {
  it('renders navigation links to tenants and devices', () => {
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Tenants' })).toHaveAttribute(
      'href',
      '/tenants',
    );
    expect(screen.getByRole('link', { name: 'Devices' })).toHaveAttribute(
      'href',
      '/devices',
    );
  });
});
