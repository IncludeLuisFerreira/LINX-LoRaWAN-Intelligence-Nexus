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

export type ApplicationFormData = z.infer<typeof schema>;

interface ApplicationFormModalProps {
  open: boolean;
  title: string;
  initial?: ApplicationFormData;
  error?: string;
  onClose: () => void;
  onSubmit: (data: ApplicationFormData) => void | Promise<void>;
}

export function ApplicationFormModal({
  open,
  title,
  initial,
  error,
  onClose,
  onSubmit,
}: ApplicationFormModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ApplicationFormData>({
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
          <Button type="submit" form="application-form" loading={isSubmitting}>
            Salvar
          </Button>
        </>
      }
    >
      <form
        id="application-form"
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-4"
      >
        {error && <Alert variant="error">{error}</Alert>}
        <Input
          label="Nome"
          placeholder="Ex: Sensores de Campo"
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
