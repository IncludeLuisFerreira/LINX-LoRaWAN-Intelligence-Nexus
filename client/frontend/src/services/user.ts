import { api } from './api';

export type UserRole = 'admin' | 'member';

export interface UserOutput {
  id: string;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  email_verified: boolean;
  note: string;
  created_at: string;
  updated_at: string;
}

export interface InviteInput {
  email: string;
  role: UserRole;
}

export interface InviteOutput {
  invite_link?: string;
  link?: string;
  invite_token?: string;
  token?: string;
}

/** Monta o link exibido na UI a partir da resposta do convite. */
export function inviteLink(invite: InviteOutput): string {
  const link = invite.invite_link ?? invite.link;
  if (link) return link;

  const token = invite.invite_token ?? invite.token;
  return token ? `${window.location.origin}/invite/${token}` : '';
}

export const userService = {
  list: async (): Promise<UserOutput[]> => {
    const response = await api.get<UserOutput[]>('/user');
    return response.data;
  },

  invite: async (orgId: string, data: InviteInput): Promise<InviteOutput> => {
    const response = await api.post<InviteOutput>(
      `/orgs/${orgId}/invite`,
      data,
    );
    return response.data;
  },

  updateRole: async (id: string, role: UserRole): Promise<UserOutput> => {
    const response = await api.patch<UserOutput>(`/user/${id}`, { role });
    return response.data;
  },

  deactivate: async (id: string): Promise<UserOutput> => {
    const response = await api.patch<UserOutput>(`/user/${id}`, {
      is_active: false,
    });
    return response.data;
  },
};
