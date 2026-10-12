import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { PageHeader } from '../../components/layout/PageHeader';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Alert } from '../../components/ui/Alert';
import { Card } from '../../components/ui/Card';
import { Spinner } from '../../components/ui/Spinner';
import { QrScanner } from '../../components/QrScanner';
import { generateAppKey, type Tr005Data } from '../../utils/tr005';
import { tenantService } from '../../services/tenant';
import { loadApplicationsByTenant, type AppOption } from '../../services/app';
import { deviceService } from '../../services/device';
import {
  deviceProfileService,
  matchProfileId,
  profileFallbackWarning,
  type DeviceProfileOutput,
} from '../../services/deviceProfile';
import { useAsyncData } from '../../hooks/useAsyncData';
import { getErrorMessage } from '../../services/api';

const schema = z.object({
  dev_eui: z
    .string()
    .regex(/^[0-9a-fA-F]{16}$/, 'Deve ter 16 caracteres hexadecimais'),
  join_eui: z
    .string()
    .regex(/^[0-9a-fA-F]{16}$/, 'Deve ter 16 caracteres hexadecimais'),
  app_key: z
    .string()
    .regex(/^[0-9a-fA-F]{32}$/, 'Deve ter 32 caracteres hexadecimais'),
  app_id: z.string().min(1, 'Selecione uma aplicação'),
  device_profile_id: z.string().min(1, 'Selecione um device profile'),
  nickname: z.string().max(50, 'Máximo de 50 caracteres').optional(),
});

type FormData = z.infer<typeof schema>;

async function loadApps(): Promise<AppOption[]> {
  const tenants = await tenantService.list();
  const appsByTenant = await loadApplicationsByTenant(tenants);
  return tenants.flatMap((tenant) =>
    (appsByTenant[tenant.id] ?? []).map((app) => ({
      id: app.id,
      label: `${tenant.name} / ${app.name}`,
    })),
  );
}

const STEP_LABELS = ['Ler QR Code', 'Confirmar dados', 'Selecionar App'];

export default function OnboardingWizard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const lockedAppId = searchParams.get('app');
  const [step, setStep] = useState(1);
  const [scanned, setScanned] = useState<Tr005Data | null>(null);
  const [profiles, setProfiles] = useState<DeviceProfileOutput[]>([]);
  const [profilesError, setProfilesError] = useState('');
  const [loadedAppId, setLoadedAppId] = useState('');
  const [profileWarning, setProfileWarning] = useState('');

  const {
    register,
    handleSubmit,
    setValue,
    setError,
    trigger,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      dev_eui: '',
      join_eui: '',
      app_key: '',
      app_id: '',
      device_profile_id: '',
      nickname: '',
    },
  });

  const {
    data: appData,
    error: appsError,
    loading: appsLoading,
  } = useAsyncData(loadApps, []);
  const apps = appData ?? [];

  const lockedAppLabel = appData?.find((app) => app.id === lockedAppId)?.label;
  const appLocked = Boolean(lockedAppId && lockedAppLabel);
  const appLockUnresolved =
    Boolean(lockedAppId) && !appsLoading && !appsError && !appLocked;

  useEffect(() => {
    if (!appLocked || !lockedAppId) return;
    setValue('app_id', lockedAppId);
  }, [appLocked, lockedAppId, setValue]);

  const appId = useWatch({ control, name: 'app_id' });
  const profilesLoading = Boolean(appId) && loadedAppId !== appId;

  useEffect(() => {
    if (!appId) return;
    let active = true;
    deviceProfileService
      .listByApp(appId)
      .then((data) => {
        if (!active) return;
        setProfiles(data);
        setProfilesError('');
        setValue('device_profile_id', matchProfileId(data, scanned?.profileId));
        setProfileWarning(profileFallbackWarning(data, scanned?.profileId));
      })
      .catch((err: unknown) => {
        if (active) setProfilesError(getErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoadedAppId(appId);
      });
    return () => {
      active = false;
    };
  }, [appId, scanned, setValue]);

  function handleDecoded(data: Tr005Data) {
    setScanned(data);
    setValue('dev_eui', data.devEUI);
    setValue('join_eui', data.joinEUI);
    setValue('app_key', generateAppKey());
    setStep(2);
  }

  async function goToStep3() {
    const valid = await trigger(['dev_eui', 'join_eui', 'app_key']);
    if (valid) setStep(3);
  }

  async function submit(values: FormData) {
    try {
      await deviceService.create({
        dev_eui: values.dev_eui,
        join_eui: values.join_eui,
        app_key: values.app_key,
        app_id: values.app_id,
        device_profile_id: values.device_profile_id,
        nickname: values.nickname?.trim() ? values.nickname.trim() : undefined,
      });
      navigate('/devices');
    } catch (err) {
      setError('root', { message: getErrorMessage(err) });
    }
  }

  const profileOptions = profiles.map((profile) => ({
    value: profile.id,
    label: profile.name,
  }));

  const noProfiles =
    Boolean(appId) && !profilesLoading && !profilesError && profiles.length === 0;
  const canSubmit =
    Boolean(appId) &&
    !profilesLoading &&
    !profilesError &&
    profiles.length > 0;

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader
        title="Onboarding de Device"
        description="Cadastre um dispositivo lendo o QR Code TR005 em 3 passos."
      />

      <ol className="mb-6 flex items-center gap-2 text-xs font-medium">
        {STEP_LABELS.map((label, index) => {
          const number = index + 1;
          const active = number === step;
          const done = number < step;
          return (
            <li key={label} className="flex items-center gap-2">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full ${
                  active || done
                    ? 'bg-primary-500 text-white'
                    : 'bg-slate-200 text-slate-500'
                }`}
              >
                {number}
              </span>
              <span className={active ? 'text-slate-800' : 'text-slate-500'}>
                {label}
              </span>
              {number < STEP_LABELS.length && (
                <span className="mx-1 text-slate-300">/</span>
              )}
            </li>
          );
        })}
      </ol>

      <Card>
        {step === 1 && (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Passo 1 de 3 — aponte a câmera para o QR Code ou cole o código
              manualmente.
            </p>
            <QrScanner
              onDecoded={handleDecoded}
              onClose={() => navigate('/devices')}
            />
          </div>
        )}

        {step === 2 && (
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              goToStep3();
            }}
          >
            <p className="text-sm text-muted">
              Passo 2 de 3 — confira e ajuste os dados lidos do QR Code.
            </p>
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
            <p className="-mt-2 text-xs text-gray-500">
              AppKey gerada localmente. Programe este mesmo valor no dispositivo
              antes do join (OTAA).
            </p>
            <Input
              label="Nickname (opcional)"
              placeholder="Ex: Sensor Galpão"
              error={errors.nickname?.message}
              {...register('nickname')}
            />
            <Input
              label="ProfileID (QR Code)"
              name="qr-profile-id"
              value={scanned?.profileId ?? ''}
              readOnly
            />
          </form>
        )}

        {step === 3 && (
          <form
            id="onboarding-form"
            className="space-y-4"
            onSubmit={handleSubmit(submit)}
          >
            <p className="text-sm text-muted">
              Passo 3 de 3 — escolha a aplicação de destino e envie.
            </p>
            {errors.root && (
              <Alert variant="error">{errors.root.message}</Alert>
            )}
            {appsLoading && (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            )}
            {!appsLoading && appsError && (
              <Alert variant="error">{appsError}</Alert>
            )}
            {appLockUnresolved && apps.length > 0 && (
              <Alert variant="info">
                A aplicação informada no link não foi encontrada. Selecione a
                aplicação de destino manualmente.
              </Alert>
            )}
            {!appsLoading && !appsError && appLocked && (
              <Input
                label="Aplicação"
                name="app-label"
                value={lockedAppLabel ?? ''}
                readOnly
              />
            )}
            {!appsLoading &&
              !appsError &&
              !appLocked &&
              (apps.length === 0 ? (
                <Alert variant="info">
                  Nenhuma aplicação disponível. Crie uma aplicação antes de
                  provisionar dispositivos.
                </Alert>
              ) : (
                <Select
                  label="Aplicação"
                  placeholder="Selecione uma aplicação"
                  options={apps.map((app) => ({
                    value: app.id,
                    label: app.label,
                  }))}
                  error={errors.app_id?.message}
                  {...register('app_id')}
                />
              ))}
            {appId && profilesLoading && (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            )}
            {appId && !profilesLoading && profiles.length > 0 && (
              <Select
                label="Device Profile"
                placeholder="Selecione um perfil"
                options={profileOptions}
                error={errors.device_profile_id?.message}
                {...register('device_profile_id')}
              />
            )}
            {appId && !profilesLoading && profileWarning && (
              <Alert variant="info">{profileWarning}</Alert>
            )}
            {appId && !profilesLoading && profilesError && (
              <Alert variant="error">{profilesError}</Alert>
            )}
            {noProfiles && (
              <Alert variant="info">
                Nenhum device profile nesta aplicação. Crie um device profile
                antes de provisionar dispositivos.
              </Alert>
            )}
          </form>
        )}
      </Card>

      <div className="mt-6 flex justify-between">
        <Button
          variant="secondary"
          onClick={() => setStep((current) => current - 1)}
          disabled={step === 1 || isSubmitting}
        >
          Voltar
        </Button>

        {step === 2 && <Button onClick={goToStep3}>Continuar</Button>}

        {step === 3 && (
          <Button
            type="submit"
            form="onboarding-form"
            loading={isSubmitting}
            disabled={!canSubmit}
          >
            Cadastrar device
          </Button>
        )}
      </div>
    </div>
  );
}
