import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Tabs } from './Tabs';

const tabs = [
  { id: 'apps', label: 'Applications', content: <p>Lista de apps</p> },
  { id: 'settings', label: 'Configurações', content: <p>Editar tenant</p> },
];

describe('Tabs', () => {
  it('renders the active tab content only', () => {
    render(<Tabs tabs={tabs} active="apps" onChange={() => {}} />);

    expect(screen.getByText('Lista de apps')).toBeInTheDocument();
    expect(screen.queryByText('Editar tenant')).not.toBeInTheDocument();
  });

  it('calls onChange with the clicked tab id', async () => {
    const onChange = vi.fn();
    render(<Tabs tabs={tabs} active="apps" onChange={onChange} />);

    await userEvent.click(screen.getByRole('tab', { name: 'Configurações' }));

    expect(onChange).toHaveBeenCalledWith('settings');
  });
});
