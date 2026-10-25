import { useEffect, useState } from 'react';
import { applicationService, type ProvisioningStatusValue } from '../services/app';
import { getErrorMessage } from '../services/api';

export const PROVISIONING_POLL_INTERVAL_MS = 3000;

/**
 * Número de falhas consecutivas (rede, 404 do backend não implementado ou
 * valor fora do contrato) que interrompem o polling. Sem esse limite o hook
 * consultaria para sempre um endpoint inexistente, silenciosamente.
 */
export const MAX_CONSECUTIVE_FAILURES = 3;

export interface ProvisioningStatusState {
  status: ProvisioningStatusValue | null;
  /** `true` enquanto a consulta do tick está em andamento. */
  loading: boolean;
  /** Último erro convertido com `getErrorMessage`; limpo no próximo sucesso. */
  error: string | null;
}

/**
 * Consulta o status de provisionamento da aplicação a cada 3s, com a primeira
 * consulta imediata no mount.
 *
 * O polling continua enquanto o status for `PENDING` ou `PROVISIONING` e para
 * ao atingir `RUNNING` ou `ERROR`. O intervalo é limpo ao desmontar ou quando
 * o `appId` muda. Falhas de rede são toleradas individualmente, mas falhas
 * consecutivas (`MAX_CONSECUTIVE_FAILURES`) interrompem o polling e são
 * sinalizadas em `error`.
 */
export function useProvisioningStatus(
  appId: string,
  intervalMs: number = PROVISIONING_POLL_INTERVAL_MS,
): ProvisioningStatusState {
  const [state, setState] = useState<{
    appId: string;
    status: ProvisioningStatusValue | null;
    loading: boolean;
    error: string | null;
  }>({ appId, status: null, loading: false, error: null });

  useEffect(() => {
    if (!appId) return;

    let active = true;
    let inFlight = false;
    let failures = 0;
    let stopped = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    const stop = () => {
      if (timer !== undefined) {
        clearInterval(timer);
        timer = undefined;
      }
    };

    const poll = async () => {
      if (!active || inFlight || stopped) return;

      inFlight = true;
      setState((prev) =>
        prev.appId === appId ? { ...prev, loading: true } : prev,
      );

      try {
        const nextStatus = await applicationService.getStatus(appId);
        if (!active) return;

        failures = 0;
        setState({
          appId,
          status: nextStatus,
          loading: false,
          error: null,
        });
        if (nextStatus === 'RUNNING' || nextStatus === 'ERROR') stop();
      } catch (error) {
        if (!active) return;

        failures += 1;
        setState((prev) =>
          prev.appId === appId
            ? { appId, status: prev.status, loading: false, error: getErrorMessage(error) }
            : prev,
        );
        if (failures >= MAX_CONSECUTIVE_FAILURES) stopped = true;
      } finally {
        inFlight = false;
      }
    };

    void poll();
    timer = setInterval(poll, intervalMs);

    return () => {
      active = false;
      stop();
    };
  }, [appId, intervalMs]);

  return {
    status: state.appId === appId ? state.status : null,
    loading: state.appId === appId ? state.loading : false,
    error: state.appId === appId ? state.error : null,
  };
}
