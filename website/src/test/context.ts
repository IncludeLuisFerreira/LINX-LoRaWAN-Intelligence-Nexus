import type { AstroCookies } from 'astro';

export function createCookies(initial: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(initial));
  const cookies = {
    get: (name: string) => {
      const value = store.get(name);
      return value === undefined ? undefined : { value };
    },
    set: (name: string, value: string) => {
      store.set(name, value);
    },
    delete: (name: string) => {
      store.delete(name);
    },
  } as unknown as AstroCookies;
  return { cookies, store };
}

export function createRedirect() {
  return (location: string, status = 302) =>
    new Response(null, { status, headers: { location } });
}
