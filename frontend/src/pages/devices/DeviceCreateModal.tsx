import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Alert } from '../../components/ui/Alert';
import {
  deviceService,
  type DeviceOutput,
} from '../../services/device';
import { getErrorMessage } from '../../services/api';

const schema = z.object({
  app_id: z.string().min(1, 'Selecione uma aplicação'),
  dev_eui: z
    .string()
    .regex(/^[0-9a-fA-F]{16}$/, 'Deve ter 16 caracteres hexadecimais'),
  join_eui: z
    .string()
    .regex(/^[0-9a-fA-F]{16}$/, 'Deve ter 16 caracteres hexadecimais'),
  app_key: z
    .string()
    .regex(/^[0-9a-fA-F]{32}$/, 'Deve ter 32 caracteres hexadecimais'),
});

type FormData = z.infer<typeof schema>;

export interface AppOption {
  id: string;
  label: string;
}

interface DeviceCreateModalProps {
  open: boolean;
  apps: AppOption[];
  onClose: () => void;
  onCreated: (device: DeviceOutput) => void;
}

export function DeviceCreateModal({
  open,
  apps,
  onClose,
  onCreated,
}: DeviceCreateModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      app_id: '',
      dev_eui: '',
      join_eui: '',
      app_key: '',
    },
  });

  useEffect(() => {
    if (open) {
      reset({ app_id: '', dev_eui: '', join_eui: '', app_key: '' });
    }
  }, [open, reset]);

  async function submit(values: FormData) {
    try {
      const device = await deviceService.create(values);
      onCreated(device);
      onClose();
    } catch (err) {
      setError('root', { message: getErrorMessage(err) });
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Novo Device"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancelar
          </Button>
          <Button type="submit" form="global-device-form" loading={isSubmitting}>
            Criar
          </Button>
        </>
      }
    >
      <form
        id="global-device-form"
        onSubmit={handleSubmit(submit)}
        className="space-y-4"
      >
        {errors.root && <Alert variant="error">{errors.root.message}</Alert>}
        <Select
          label="Aplicação"
          placeholder="Selecione uma aplicação"
          options={apps.map((app) => ({ value: app.id, label: app.label }))}
          error={errors.app_id?.message}
          {...register('app_id')}
        />
        <Input
          label="DevEUI"
          placeholder="16 caracteres hexadecimais"
          error={errors.dev_eui?.message}
          {...register('dev_eui')}
        />
        <Input
          label="JoinEUI"
          placeholder="16 caracteres hexadecimais"
          error={errors.join_eui?.message}
          {...register('join_eui')}
        />
        <Input
          label="AppKey"
          placeholder="32 caracteres hexadecimais"
          error={errors.app_key?.message}
          {...register('app_key')}
        />
      </form>
    </Modal>
  );
}
