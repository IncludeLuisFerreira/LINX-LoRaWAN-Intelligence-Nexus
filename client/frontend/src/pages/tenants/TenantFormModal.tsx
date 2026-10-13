import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Alert } from '../../components/ui/Alert';

const schema = z.object({
  name: z.string().min(2, 'O nome deve ter pelo menos 2 caracteres'),
  description: z.string().optional(),
});

export type TenantFormData = z.infer<typeof schema>;

interface TenantFormModalProps {
  open: boolean;
  title: string;
  initial?: TenantFormData;
  error?: string;
  onClose: () => void;
  onSubmit: (data: TenantFormData) => void | Promise<void>;
}

export function TenantFormModal({
  open,
  title,
  initial,
  error,
  onClose,
  onSubmit,
}: TenantFormModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TenantFormData>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', description: '' },
  });

  useEffect(() => {
    if (open) reset(initial ?? { name: '', description: '' });
  }, [open, initial, reset]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancelar
          </Button>
          <Button
            type="submit"
            form="tenant-form"
            loading={isSubmitting}
          >
            Salvar
          </Button>
        </>
      }
    >
      <form
        id="tenant-form"
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-4"
      >
        {error && <Alert variant="error">{error}</Alert>}
        <Input
          label="Nome"
          placeholder="Ex: ACME"
          error={errors.name?.message}
          {...register('name')}
        />
        <Input
          label="Descrição"
          placeholder="Opcional"
          error={errors.description?.message}
          {...register('description')}
        />
      </form>
    </Modal>
  );
}
