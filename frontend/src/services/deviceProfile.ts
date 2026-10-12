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
