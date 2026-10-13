import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfirmDialog } from './ConfirmDialog';

describe('ConfirmDialog', () => {
  it('shows the title and message when open', () => {
    render(
      <ConfirmDialog
        open
        title="Excluir tenant"
        message="Esta ação é irreversível."
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );

    expect(screen.getByText('Excluir tenant')).toBeInTheDocument();
    expect(screen.getByText('Esta ação é irreversível.')).toBeInTheDocument();
  });

  it('calls onConfirm on confirm and onCancel on cancel', async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Excluir"
        message="msg"
        confirmLabel="Excluir"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Excluir' }));
    expect(onConfirm).toHaveBeenCalledOnce();

    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('renders nothing when closed', () => {
    render(
      <ConfirmDialog
        open={false}
        title="Excluir"
        message="msg"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );

    expect(screen.queryByText('Excluir')).not.toBeInTheDocument();
  });
});
