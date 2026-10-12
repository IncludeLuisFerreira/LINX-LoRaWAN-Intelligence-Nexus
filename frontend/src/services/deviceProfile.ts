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
export function matchProfileId(
  profiles: DeviceProfileOutput[],
  profileId: string | undefined,
): string {
  const fallback = profiles[0]?.id ?? '';
  if (!profileId) return fallback;
  const target = profileId.trim().toUpperCase();
  if (!target || target === PROFILE_ID_DEFAULT) return fallback;
  const found = profiles.find(
    (profile) =>
      profile.id.trim().toUpperCase() === target ||
      profile.name.trim().toUpperCase() === target,
  );
  return found?.id ?? fallback;
}
