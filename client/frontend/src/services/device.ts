import { api } from './api';

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
  listByApp: async (appId: string): Promise<DeviceOutput[]> => {
    const response = await api.get<DeviceOutput[]>('/devices', {
      params: { app_id: appId },
    });
    return response.data;
  },

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
