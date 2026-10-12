import { useEffect, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
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
import {
  deviceProfileService,
  type DeviceProfileOutput,
} from '../../services/deviceProfile';
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
  device_profile_id: z.string().min(1, 'Selecione um device profile'),
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
  const [profiles, setProfiles] = useState<DeviceProfileOutput[]>([]);
  const [profilesError, setProfilesError] = useState('');
  const {
    register,
    handleSubmit,
    reset,
    setError,
    setValue,
    getValues,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      app_id: '',
      dev_eui: '',
      join_eui: '',
      app_key: '',
      device_profile_id: '',
    },
  });

  const appId = useWatch({ control, name: 'app_id' });

  useEffect(() => {
    if (!open) return;
    reset({
      app_id: '',
      dev_eui: '',
      join_eui: '',
      app_key: '',
      device_profile_id: '',
    });
  }, [open, reset]);

  useEffect(() => {
    if (!open || !appId) {
      setProfiles([]);
      return;
    }
    let active = true;
    deviceProfileService
      .listByApp(appId)
      .then((data) => {
        if (!active) return;
        setProfiles(data);
        setProfilesError('');
        if (!getValues('device_profile_id')) {
          setValue('device_profile_id', data[0]?.id ?? '');
        }
      })
      .catch((err: unknown) => {
        if (active) setProfilesError(getErrorMessage(err));
      });
    return () => {
      active = false;
    };
  }, [open, appId, setValue]);

  const profileOptions = profiles.map((profile) => ({
    value: profile.id,
    label: profile.name,
  }));

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
        <Select
          label="Device Profile"
          placeholder="Selecione um perfil"
          options={profileOptions}
          error={errors.device_profile_id?.message}
          {...register('device_profile_id')}
        />
        {profilesError && <Alert variant="error">{profilesError}</Alert>}
      </form>
    </Modal>
  );
}
