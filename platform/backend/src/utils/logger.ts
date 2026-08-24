const ts = (): string => new Date().toISOString()

export const logger = {
  info: (msg: string): void => console.log(`[${ts()}] [info] ${msg}`),
  warn: (msg: string): void => console.warn(`[${ts()}] [warn] ${msg}`),
  error: (msg: string, err?: unknown): void =>
    console.error(`[${ts()}] [error] ${msg}`, err instanceof Error ? err.stack ?? err.message : err ?? ''),
}
