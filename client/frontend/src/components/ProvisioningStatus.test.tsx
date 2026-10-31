import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProvisioningStatus } from './ProvisioningStatus';

describe('ProvisioningStatus', () => {
  it.each([
    ['PENDING', 'Pendente', 'bg-gray-100', 'text-gray-600'],
    ['PROVISIONING', 'Provisionando', 'bg-yellow-100', 'text-yellow-700'],
    ['RUNNING', 'Em execução', 'bg-green-100', 'text-green-700'],
    ['ERROR', 'Erro', 'bg-red-100', 'text-red-700'],
  ] as const)(
    'renders %s with the expected label and colors',
    (status, label, backgroundClass, textClass) => {
      render(<ProvisioningStatus status={status} />);

      const badge = screen.getByRole('status');

      expect(badge).toHaveTextContent(label);
      expect(badge).toHaveClass(backgroundClass, textClass);
    },
  );

  it('pulses while provisioning', () => {
    render(<ProvisioningStatus status="PROVISIONING" />);

    expect(screen.getByRole('status')).toHaveClass('animate-pulse');
  });

  it('does not pulse for the other states', () => {
    const { rerender } = render(<ProvisioningStatus status="PENDING" />);

    expect(screen.getByRole('status')).not.toHaveClass('animate-pulse');

    rerender(<ProvisioningStatus status="RUNNING" />);
    expect(screen.getByRole('status')).not.toHaveClass('animate-pulse');

    rerender(<ProvisioningStatus status="ERROR" />);
    expect(screen.getByRole('status')).not.toHaveClass('animate-pulse');
  });

  it('is announced as a polite status and keeps custom classes', () => {
    render(<ProvisioningStatus status="RUNNING" className="custom-class" />);

    const badge = screen.getByRole('status');

    expect(badge).toHaveAttribute('aria-live', 'polite');
    expect(badge).toHaveClass('custom-class');
  });
});
