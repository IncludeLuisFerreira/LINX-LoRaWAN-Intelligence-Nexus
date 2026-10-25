import { useEffect, useState } from 'react';
import {
  applicationService,
  type ProvisioningStatusValue,
} from '../services/app';

export const PROVISIONING_POLL_INTERVAL_MS = 3000;

interface ProvisioningStatusState {
  status: ProvisioningStatusValue | null;
}

/**
 * Consulta o status de provisionamento da aplicação a cada 3s.
 *
 * O polling continua enquanto o status for `PENDING` ou `PROVISIONING` e para
 * ao atingir `RUNNING` ou `ERROR`. O intervalo é limpo ao desmontar ou quando
 * o `appId` muda. Falhas de rede não interrompem o polling.
 */
export function useProvisioningStatus(
  appId: string,
  intervalMs: number = PROVISIONING_POLL_INTERVAL_MS,
): ProvisioningStatusState {
  const [state, setState] = useState<{
    appId: string;
    status: ProvisioningStatusValue | null;
  }>({ appId, status: null });

  useEffect(() => {
    if (!appId) return;

    let active = true;
    let inFlight = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    const stop = () => {
      if (timer !== undefined) {
        clearInterval(timer);
        timer = undefined;
      }
    };

    const poll = async () => {
      if (!active || inFlight) return;

      inFlight = true;
      try {
        const nextStatus = await applicationService.getStatus(appId);
        if (!active) return;

        setState({ appId, status: nextStatus });
        if (nextStatus === 'RUNNING' || nextStatus === 'ERROR') stop();
      } catch {
        /* rede indisponível: mantém o polling para o próximo tick */
      } finally {
        inFlight = false;
      }
    };

    timer = setInterval(poll, intervalMs);

    return () => {
      active = false;
      stop();
    };
  }, [appId, intervalMs]);

  return {
    status: appId && state.appId === appId ? state.status : null,
  };
}
