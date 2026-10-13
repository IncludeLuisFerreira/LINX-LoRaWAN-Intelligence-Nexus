import { describe, it, expect } from 'vitest';
import {
  parseTr005,
  generateAppKey,
  isValidTr005,
  Tr005ParseError,
} from './tr005';

describe('parseTr005', () => {
  const JOIN = '1122334455667788';
  const DEV = 'AABBCCDDEEFF0011';
  const PROFILE = 'AABB1122';

  describe('payloads válidos do spec', () => {
    it('extrai os 4 campos do exemplo mínimo do spec', () => {
      const qr = `LW:D0:${JOIN}:${DEV}:${PROFILE}`;
      const result = parseTr005(qr);

      expect(result.schemaId).toBe('D0');
      expect(result.joinEUI).toBe(JOIN);
      expect(result.devEUI).toBe(DEV);
      expect(result.profileId).toBe(PROFILE);
    });

    it('extrai campos e ignora extensões do exemplo com extensões', () => {
      const qr =
        `LW:D0:${JOIN}:${DEV}:${PROFILE}` +
        ':OAABBCCDDEEFF:SYYWWNNNNNN:PFOOBAR:CAF2C';
      const result = parseTr005(qr);

      expect(result).toEqual({
        schemaId: 'D0',
        joinEUI: JOIN,
        devEUI: DEV,
        profileId: PROFILE,
      });
    });

    it('não retorna appKey (AppKey não faz parte do TR005)', () => {
      const result = parseTr005(`LW:D0:${JOIN}:${DEV}:${PROFILE}`);

      expect(result).not.toHaveProperty('appKey');
    });

    it("usa default '00000000' quando ProfileID está ausente (3 campos)", () => {
      const result = parseTr005(`LW:D0:${JOIN}:${DEV}`);

      expect(result.profileId).toBe('00000000');
    });
  });

  describe('tolerância de formato', () => {
    it("aceita payload sem prefixo 'LW' com separadores", () => {
      const qr = `D0:${JOIN}:${DEV}:${PROFILE}`;
      const result = parseTr005(qr);

      expect(result.schemaId).toBe('D0');
      expect(result.joinEUI).toBe(JOIN);
      expect(result.devEUI).toBe(DEV);
      expect(result.profileId).toBe(PROFILE);
    });

    it('aceita payload sem prefixo e sem ProfileID', () => {
      const result = parseTr005(`D0:${JOIN}:${DEV}`);

      expect(result.profileId).toBe('00000000');
    });

    it("aceita separador '-' no lugar de ':'", () => {
      const qr = `LW-D0-${JOIN}-${DEV}-${PROFILE}`;
      const result = parseTr005(qr);

      expect(result.joinEUI).toBe(JOIN);
      expect(result.devEUI).toBe(DEV);
      expect(result.profileId).toBe(PROFILE);
    });

    it('normaliza minúsculas para uppercase', () => {
      const qr = `lw:d0:${JOIN.toLowerCase()}:${DEV.toLowerCase()}:${PROFILE.toLowerCase()}`;
      const result = parseTr005(qr);

      expect(result.schemaId).toBe('D0');
      expect(result.joinEUI).toBe(JOIN);
      expect(result.devEUI).toBe(DEV);
      expect(result.profileId).toBe(PROFILE);
    });

    it('remove espaços nas pontas', () => {
      const result = parseTr005(`   LW:D0:${JOIN}:${DEV}:${PROFILE}   `);

      expect(result.joinEUI).toBe(JOIN);
    });

    it('remove espaços internos (ao redor dos separadores)', () => {
      const qr = `LW : D0 : ${JOIN} : ${DEV} : ${PROFILE}`;
      const result = parseTr005(qr);

      expect(result.schemaId).toBe('D0');
      expect(result.joinEUI).toBe(JOIN);
      expect(result.devEUI).toBe(DEV);
      expect(result.profileId).toBe(PROFILE);
    });
  });

  describe('formato compacto (sem separadores)', () => {
    it("aceita compacto 'D0' + 32 hex → profileId default", () => {
      const compact = `D0${JOIN}${DEV}`;
      const result = parseTr005(compact);

      expect(result.schemaId).toBe('D0');
      expect(result.joinEUI).toBe(JOIN);
      expect(result.devEUI).toBe(DEV);
      expect(result.profileId).toBe('00000000');
    });

    it("aceita compacto 'D0' + 40 hex → profileId extraído", () => {
      const compact = `D0${JOIN}${DEV}${PROFILE}`;
      const result = parseTr005(compact);

      expect(result.profileId).toBe(PROFILE);
    });

    it("aceita compacto com prefixo 'LWD0'", () => {
      const compact = `LWD0${JOIN}${DEV}${PROFILE}`;
      const result = parseTr005(compact);

      expect(result.schemaId).toBe('D0');
      expect(result.joinEUI).toBe(JOIN);
      expect(result.devEUI).toBe(DEV);
      expect(result.profileId).toBe(PROFILE);
    });
  });

  describe('erros — entrada vazia', () => {
    it('rejeita string vazia', () => {
      expect(() => parseTr005('')).toThrow(Tr005ParseError);
      expect(() => parseTr005('')).toThrow(/QR Code vazio ou inválido/);
    });

    it('rejeita valor não-string', () => {
      expect(() => parseTr005(null as unknown as string)).toThrow(
        Tr005ParseError,
      );
      expect(() => parseTr005(undefined as unknown as string)).toThrow(
        /QR Code vazio ou inválido/,
      );
    });
  });

  describe('erros — SchemaID', () => {
    it("rejeita SchemaID 'D1' com mensagem 'não suportado'", () => {
      expect(() => parseTr005(`LW:D1:${JOIN}:${DEV}:${PROFILE}`)).toThrow(
        Tr005ParseError,
      );
      expect(() => parseTr005(`LW:D1:${JOIN}:${DEV}:${PROFILE}`)).toThrow(
        /SchemaID "D1" não suportado\. Esperado "D0"\./,
      );
    });

    it("rejeita SchemaID 'C0'", () => {
      expect(() => parseTr005(`LW:C0:${JOIN}:${DEV}:${PROFILE}`)).toThrow(
        /SchemaID "C0" não suportado/,
      );
    });
  });

  describe('erros — JoinEUI', () => {
    it('rejeita JoinEUI com 15 caracteres', () => {
      expect(() =>
        parseTr005(`LW:D0:112233445566778:${DEV}:${PROFILE}`),
      ).toThrow(/JoinEUI inválido/);
    });

    it('rejeita JoinEUI com caractere não-hex', () => {
      expect(() =>
        parseTr005(`LW:D0:ABCDEF012345678G:${DEV}:${PROFILE}`),
      ).toThrow(/JoinEUI inválido/);
    });
  });

  describe('erros — DevEUI', () => {
    it('rejeita DevEUI com 17 caracteres', () => {
      expect(() =>
        parseTr005(`LW:D0:${JOIN}:AABBCCDDEEFF00112:${PROFILE}`),
      ).toThrow(/DevEUI inválido/);
    });

    it('rejeita DevEUI com caractere não-hex', () => {
      expect(() =>
        parseTr005(`LW:D0:${JOIN}:0123456789ABCDEG:${PROFILE}`),
      ).toThrow(/DevEUI inválido/);
    });
  });

  describe('erros — ProfileID', () => {
    it('rejeita ProfileID presente mas inválido (tamanho errado)', () => {
      expect(() => parseTr005(`LW:D0:${JOIN}:${DEV}:ZZ`)).toThrow(
        /ProfileID inválido/,
      );
    });

    it('rejeita ProfileID não-hex com tamanho 8', () => {
      expect(() => parseTr005(`LW:D0:${JOIN}:${DEV}:ABCDEFGH`)).toThrow(
        Tr005ParseError,
      );
      expect(() => parseTr005(`LW:D0:${JOIN}:${DEV}:ABCDEFGH`)).toThrow(
        /ProfileID inválido/,
      );
    });
  });

  describe('erros — payload curto/formato', () => {
    it("rejeita 'LW' sozinho", () => {
      expect(() => parseTr005('LW')).toThrow(Tr005ParseError);
      expect(() => parseTr005('LW')).toThrow(/Formato TR005 inválido/);
    });

    it("rejeita payload só 'LW:D0'", () => {
      expect(() => parseTr005('LW:D0')).toThrow(/Formato TR005 inválido/);
    });

    it('rejeita compacto curto (menos de 34 chars)', () => {
      expect(() => parseTr005(`D0${JOIN}`)).toThrow(/Formato TR005 inválido/);
    });

    it('rejeita texto lixo', () => {
      expect(() => parseTr005('hello world')).toThrow(Tr005ParseError);
    });
  });
});

describe('generateAppKey', () => {
  it('gera AppKey com 32 caracteres hexadecimais maiúsculos', () => {
    const appKey = generateAppKey();

    expect(appKey).toHaveLength(32);
    expect(appKey).toMatch(/^[0-9A-F]{32}$/);
  });

  it('gera chave em uppercase', () => {
    const appKey = generateAppKey();

    expect(appKey).toBe(appKey.toUpperCase());
  });

  it('gera chaves diferentes a cada chamada', () => {
    const key1 = generateAppKey();
    const key2 = generateAppKey();

    expect(key1).not.toBe(key2);
  });
});

describe('isValidTr005', () => {
  const JOIN = '1122334455667788';
  const DEV = 'AABBCCDDEEFF0011';
  const PROFILE = 'AABB1122';

  it('retorna true para o exemplo completo do spec', () => {
    const full = `LW:D0:${JOIN}:${DEV}:${PROFILE}:OAABBCCDDEEFF:SYYWWNNNNNN:PFOOBAR:CAF2C`;
    expect(isValidTr005(full)).toBe(true);
  });

  it('retorna true para o payload mínimo', () => {
    expect(isValidTr005(`LW:D0:${JOIN}:${DEV}:${PROFILE}`)).toBe(true);
  });

  it('retorna true para payload mínimo sem ProfileID', () => {
    expect(isValidTr005(`LW:D0:${JOIN}:${DEV}`)).toBe(true);
  });

  it('retorna true para formato compacto', () => {
    expect(isValidTr005(`D0${JOIN}${DEV}`)).toBe(true);
  });

  it("retorna false para 'invalid'", () => {
    expect(isValidTr005('invalid')).toBe(false);
  });

  it('retorna false para string vazia', () => {
    expect(isValidTr005('')).toBe(false);
  });

  it("retorna false para 'D0' sozinho", () => {
    expect(isValidTr005('D0')).toBe(false);
  });

  it('retorna false para SchemaID errado', () => {
    expect(isValidTr005(`LW:D1:${JOIN}:${DEV}:${PROFILE}`)).toBe(false);
  });
});
