import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TenantFormModal } from './TenantFormModal';

function renderModal(
  onSubmit = vi.fn(),
  onClose = vi.fn(),
  props: Partial<Parameters<typeof TenantFormModal>[0]> = {},
) {
  render(
    <TenantFormModal
      open
      title="Novo Tenant"
      onClose={onClose}
      onSubmit={onSubmit}
      {...props}
    />,
  );
  return { onSubmit, onClose };
}

describe('TenantFormModal', () => {
  it('renders title, name and description fields', () => {
    renderModal();
    expect(screen.getByText('Novo Tenant')).toBeInTheDocument();
    expect(screen.getByLabelText('Nome')).toBeInTheDocument();
    expect(screen.getByLabelText('Descrição')).toBeInTheDocument();
  });

  it('calls onClose when Cancelar is clicked', async () => {
    const { onClose } = renderModal();
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('shows Zod error when name is too short', async () => {
    renderModal();
    await userEvent.type(screen.getByLabelText('Nome'), 'a');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    expect(
      await screen.findByText('O nome deve ter pelo menos 2 caracteres'),
    ).toBeInTheDocument();
  });

  it('calls onSubmit with form values on valid submission', async () => {
    const { onSubmit } = renderModal();
    await userEvent.type(screen.getByLabelText('Nome'), 'ACME');
    await userEvent.type(screen.getByLabelText('Descrição'), 'desc');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit.mock.calls[0][0]).toEqual({ name: 'ACME', description: 'desc' });
  });

  it('displays external error prop', () => {
    renderModal(vi.fn(), vi.fn(), { error: 'Falha no servidor' });
    expect(screen.getByText('Falha no servidor')).toBeInTheDocument();
  });

  it('pre-fills fields from initial prop', () => {
    renderModal(vi.fn(), vi.fn(), {
      initial: { name: 'Existente', description: 'desc existente' },
    });
    expect(screen.getByLabelText('Nome')).toHaveValue('Existente');
    expect(screen.getByLabelText('Descrição')).toHaveValue('desc existente');
  });
});
