import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApplicationFormModal } from './ApplicationFormModal';

function renderModal(
  onSubmit = vi.fn(),
  onClose = vi.fn(),
  props: Partial<Parameters<typeof ApplicationFormModal>[0]> = {},
) {
  render(
    <ApplicationFormModal
      open
      title="Nova Aplicação"
      onClose={onClose}
      onSubmit={onSubmit}
      {...props}
    />,
  );
  return { onSubmit, onClose };
}

describe('ApplicationFormModal', () => {
  it('renders title, name and description fields', () => {
    renderModal();
    expect(screen.getByText('Nova Aplicação')).toBeInTheDocument();
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
    await userEvent.type(screen.getByLabelText('Nome'), 'Fazenda');
    await userEvent.type(screen.getByLabelText('Descrição'), 'sensores');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit.mock.calls[0][0]).toEqual({ name: 'Fazenda', description: 'sensores' });
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
