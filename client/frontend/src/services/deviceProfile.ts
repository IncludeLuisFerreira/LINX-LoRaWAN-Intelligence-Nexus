import { api } from './api';

export interface DeviceProfileOutput {
  id: string;
  name: string;
}

export const deviceProfileService = {
  listByApp: async (appId: string): Promise<DeviceProfileOutput[]> => {
    const response = await api.get<DeviceProfileOutput[]>('/device-profile/', {
      params: { app_id: appId },
    });
    return response.data;
  },
};

/** Default de ProfileID quando o QR não traz perfil (perfil por omissão). */
const PROFILE_ID_DEFAULT = '00000000';

/**
 * Casa o ProfileID lido do QR TR005 contra os device profiles do tenant.
 * O backend só expõe `{ id, name }`, então tenta o id e o nome
 * (case-insensitive). Sem correspondência, usa o primeiro perfil.
 */
function findProfile(
  profiles: DeviceProfileOutput[],
  profileId: string | undefined,
): DeviceProfileOutput | undefined {
  if (!profileId) return undefined;
  const target = profileId.trim().toUpperCase();
  if (!target || target === PROFILE_ID_DEFAULT) return undefined;
  return profiles.find(
    (profile) =>
      profile.id.trim().toUpperCase() === target ||
      profile.name.trim().toUpperCase() === target,
  );
}

export function matchProfileId(
  profiles: DeviceProfileOutput[],
  profileId: string | undefined,
): string {
  return findProfile(profiles, profileId)?.id ?? profiles[0]?.id ?? '';
}

/**
 * Mensagem de alerta quando o ProfileID do QR é explícito mas não casa com
 * nenhum perfil da aplicação — o wizard cai no primeiro perfil e precisa avisar
 * para evitar um provisionamento OTAA silenciosamente errado.
 */
export function profileFallbackWarning(
  profiles: DeviceProfileOutput[],
  profileId: string | undefined,
): string {
  if (findProfile(profiles, profileId)) return '';
  const target = profileId?.trim().toUpperCase();
  if (!target || target === PROFILE_ID_DEFAULT) return '';
  const fallback = profiles[0];
  if (!fallback) return '';
  return (
    `ProfileID do QR ("${profileId?.trim()}") não corresponde a nenhum perfil ` +
    `desta aplicação. Usando "${fallback.name}" por padrão — confirme antes de enviar.`
  );
}
