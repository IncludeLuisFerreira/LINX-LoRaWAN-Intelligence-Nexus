import { describe, expect, it } from 'vitest';
import { safeRelativePath } from './redirect';

describe('safeRelativePath', () => {
  it('usa o fallback quando o valor é ausente ou vazio', () => {
    expect(safeRelativePath(undefined)).toBe('/');
    expect(safeRelativePath(null)).toBe('/');
    expect(safeRelativePath('')).toBe('/');
  });

  it('preserva caminhos relativos same-origin', () => {
    expect(safeRelativePath('/obrigado')).toBe('/obrigado');
    expect(safeRelativePath('/conta?tab=perfil')).toBe('/conta?tab=perfil');
  });

  it('rejeita URLs absolutas', () => {
    expect(safeRelativePath('https://evil.example')).toBe('/');
    expect(safeRelativePath('javascript:alert(1)')).toBe('/');
  });

  it('rejeita caminhos scheme-relative', () => {
    expect(safeRelativePath('//evil.example')).toBe('/');
  });

  it('rejeita barras invertidas e caracteres de controle', () => {
    expect(safeRelativePath('/\\evil.example')).toBe('/');
    expect(safeRelativePath('/a\u0000b')).toBe('/');
  });

  it('usa fallback customizado quando informado', () => {
    expect(safeRelativePath('https://evil.example', '/login')).toBe('/login');
  });
});
