import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { api } from './api';
import {
  deviceProfileService,
  matchProfileId,
  profileFallbackWarning,
} from './deviceProfile';

vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mocked = api as unknown as Record<
  'get' | 'post' | 'patch' | 'delete',
  Mock
>;

describe('deviceProfileService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists device profiles of an application with GET ?app_id=', async () => {
    mocked.get.mockResolvedValue({ data: [] });

    await deviceProfileService.listByApp('app-1');

    expect(mocked.get).toHaveBeenCalledWith('/device-profile/', {
      params: { app_id: 'app-1' },
    });
  });
});

describe('matchProfileId', () => {
  const profiles = [
    { id: 'uuid-a', name: 'Perfil A' },
    { id: 'uuid-b', name: 'AABB1122' },
  ];

  it('matches by profile name (case-insensitive)', () => {
    expect(matchProfileId(profiles, 'aabb1122')).toBe('uuid-b');
  });

  it('matches by profile id', () => {
    expect(matchProfileId(profiles, 'UUID-A')).toBe('uuid-a');
  });

  it('falls back to the first profile when absent, default or unmatched', () => {
    expect(matchProfileId(profiles, undefined)).toBe('uuid-a');
    expect(matchProfileId(profiles, '00000000')).toBe('uuid-a');
    expect(matchProfileId(profiles, 'NOPE')).toBe('uuid-a');
    expect(matchProfileId([], 'AABB1122')).toBe('');
  });
});

describe('profileFallbackWarning', () => {
  const profiles = [{ id: 'uuid-a', name: 'Perfil A' }];

  it('returns no warning when the QR profile matches an entry', () => {
    expect(profileFallbackWarning(profiles, 'PERFIL A')).toBe('');
  });

  it('returns no warning when the QR has no explicit profile', () => {
    expect(profileFallbackWarning(profiles, undefined)).toBe('');
    expect(profileFallbackWarning(profiles, '00000000')).toBe('');
  });

  it('warns when an explicit QR profile falls back to the first entry', () => {
    expect(profileFallbackWarning(profiles, 'AABB1122')).toMatch(
      /não corresponde a nenhum perfil/,
    );
    expect(profileFallbackWarning(profiles, 'AABB1122')).toContain('Perfil A');
  });

  it('returns no warning when there are no profiles to fall back to', () => {
    expect(profileFallbackWarning([], 'AABB1122')).toBe('');
  });
});
