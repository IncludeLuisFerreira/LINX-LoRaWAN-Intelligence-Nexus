import { api } from './api';
import { fetchAllPages } from './pagination';

export interface DeviceOutput {
  id: string;
  dev_eui: string;
  app_id: string;
  join_eui: string;
  device_profile_id: string;
  nickname: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateDeviceInput {
  dev_eui: string;
  app_id: string;
  join_eui: string;
  app_key: string;
  device_profile_id: string;
  nickname?: string | null;
}

export const deviceService = {
  listByApp: (appId: string): Promise<DeviceOutput[]> =>
    fetchAllPages(async (skip, limit) => {
      const response = await api.get<DeviceOutput[]>('/devices', {
        params: { app_id: appId, skip, limit },
      });
      return response.data;
    }),

  create: async (payload: CreateDeviceInput): Promise<DeviceOutput> => {
    const response = await api.post<DeviceOutput>('/devices', payload);
    return response.data;
  },

  update: async (
    id: string,
    data: { nickname: string | null },
  ): Promise<DeviceOutput> => {
    const response = await api.patch<DeviceOutput>(`/devices/${id}`, data);
    return response.data;
  },

  remove: async (id: string): Promise<void> => {
    await api.delete(`/devices/${id}`);
  },
};
