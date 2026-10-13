import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Alert } from '../../components/ui/Alert';
import { deviceService, type DeviceOutput } from '../../services/device';
import { getErrorMessage } from '../../services/api';

const schema = z.object({
  nickname: z.string().max(50, 'Máximo de 50 caracteres').optional(),
});

type FormData = z.infer<typeof schema>;

interface DeviceNicknameModalProps {
  open: boolean;
  device: DeviceOutput | null;
  onClose: () => void;
  onSaved: () => void;
}

export function DeviceNicknameModal({
  open,
  device,
  onClose,
  onSaved,
}: DeviceNicknameModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { nickname: '' },
  });

  useEffect(() => {
    if (open) reset({ nickname: device?.nickname ?? '' });
  }, [open, device, reset]);

  async function submit(values: FormData) {
    if (!device) return;
    try {
      await deviceService.update(device.id, {
        nickname: values.nickname?.trim() ? values.nickname.trim() : null,
      });
      onSaved();
    } catch (err) {
      setError('root', { message: getErrorMessage(err) });
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Editar nickname"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancelar
          </Button>
          <Button
            type="submit"
            form="device-nickname-form"
            loading={isSubmitting}
          >
            Salvar
          </Button>
        </>
      }
    >
      <form
        id="device-nickname-form"
        onSubmit={handleSubmit(submit)}
        className="space-y-4"
      >
        {errors.root && <Alert variant="error">{errors.root.message}</Alert>}
        <Input
          label="Nickname"
          placeholder="Ex: Sensor Galpão"
          error={errors.nickname?.message}
          {...register('nickname')}
        />
      </form>
    </Modal>
  );
}
