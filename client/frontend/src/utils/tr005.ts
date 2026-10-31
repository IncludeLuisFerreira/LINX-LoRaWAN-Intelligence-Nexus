/**
 * Utilitário para parsing de QR Codes TR005 (LoRaWAN Backdoor Key Mechanism).
 *
 * Formato real (LoRa Alliance TR005, §4.2):
 *   LW:SchemaID:JoinEUI:DevEUI:ProfileID[:extensões...]
 *
 * Exemplos do próprio spec:
 *   - mínimo:    "LW:D0:1122334455667788:AABBCCDDEEFF0011:AABB1122"
 *   - extensões: "LW:D0:1122334455667788:AABBCCDDEEFF0011:AABB1122:OAABBCCDDEEFF:SYYWWNNNNNN:PFOOBAR:CAF2C"
 *
 * Decisão de produto (Modelo A): AppKey NÃO faz parte do QR TR005.
 * O QR fornece apenas SchemaID, JoinEUI, DevEUI e ProfileID.
 * A AppKey é gerada separadamente via generateAppKey() para o fluxo plug-and-play.
 */

/** Dados extraídos de um QR Code TR005 */
export interface Tr005Data {
  /** SchemaID (ex: "D0") */
  schemaId: string;
  /** JoinEUI / AppEUI (16 hex) */
  joinEUI: string;
  /** DevEUI (16 hex) */
  devEUI: string;
  /**
   * ProfileID (8 hex). Quando o payload não traz ProfileID,
   * usamos o default "00000000" (perfil por omissão do dispositivo).
   */
  profileId: string;
}

/** Erro de parse com mensagem amigável para o usuário */
export class Tr005ParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'Tr005ParseError';
  }
}

/** Regex para validar hexadecimal */
const HEX_REGEX = /^[0-9A-F]+$/;

/** Caracteres hexadecimais para geração aleatória */
const HEX_CHARS = '0123456789ABCDEF';

/** Default de ProfileID quando ausente no payload (perfil por omissão) */
const DEFAULT_PROFILE_ID = '00000000';

/** Mensagem canônica de formato inválido */
const FORMAT_ERROR =
  'Formato TR005 inválido. Esperado: LW:SchemaID:JoinEUI:DevEUI:ProfileID.';

/** Valida se string é hex de tamanho exato */
function isValidHex(value: string, length: number): boolean {
  return value.length === length && HEX_REGEX.test(value);
}

/**
 * Faz parse de uma string QR Code TR005.
 *
 * Aceita formatos:
 *  - "LW:D0:1122334455667788:AABBCCDDEEFF0011:AABB1122" (padrão, com prefixo)
 *  - "D0:1122334455667788:AABBCCDDEEFF0011:AABB1122"   (sem prefixo "LW")
 *  - "LW-D0-...-..."                                    (separador "-")
 *  - "LWD0" + 16hex + 16hex (+ 8hex)                    (compacto, sem separadores)
 *  - minúsculas e espaços (internos/externos) são normalizados
 *  - extensões após ProfileID são ignoradas silenciosamente
 *
 * @param text - String bruta lida do QR Code
 * @returns Tr005Data com campos normalizados (uppercase, sem separadores)
 * @throws Tr005ParseError com mensagem amigável se inválido
 */
export function parseTr005(text: string): Tr005Data {
  // Regra 1: entrada vazia / não-string
  if (!text || typeof text !== 'string') {
    throw new Tr005ParseError('QR Code vazio ou inválido.');
  }

  // Normaliza: força uppercase e remove todos os espaços (internos e externos).
  // Separadores ":" e "-" são PRESERVADOS para detecção do formato.
  let payload = text.toUpperCase().replace(/\s+/g, '');

  // Remove o prefixo opcional "LW". SchemaID ("D0") nunca contém "LW",
  // então o fatiamento é seguro mesmo no formato compacto ("LWD0...").
  if (payload.startsWith('LW')) {
    payload = payload.slice(2);
  }
  // Remove separadores que sobraram no início após a remoção do prefixo.
  payload = payload.replace(/^[-:]+/, '');

  if (payload.length < 2) {
    throw new Tr005ParseError(FORMAT_ERROR);
  }

  let schemaId: string;
  let joinEUI: string;
  let devEUI: string;
  let profileIdRaw: string | undefined;

  if (/[-:]/.test(payload)) {
    // Formato com separadores: SchemaID:JoinEUI:DevEUI[:ProfileID[:extensões...]]
    const parts = payload.split(/[-:]/);
    schemaId = parts[0] ?? '';
    joinEUI = parts[1] ?? '';
    devEUI = parts[2] ?? '';
    // parts[3] é ProfileID (opcional); extensões (parts[4+]) são ignoradas.
    profileIdRaw = parts[3];
  } else {
    // Formato compacto antigo, sem separadores:
    // SchemaID(2) + JoinEUI(16) + DevEUI(16) [+ ProfileID(8)]
    if (payload.length < 34) {
      throw new Tr005ParseError(FORMAT_ERROR);
    }
    schemaId = payload.slice(0, 2);
    joinEUI = payload.slice(2, 18);
    devEUI = payload.slice(18, 34);
    if (payload.length > 34) {
      profileIdRaw = payload.slice(34, 42);
    }
  }

  // Regra 2: SchemaID deve ser "D0"
  if (schemaId !== 'D0') {
    throw new Tr005ParseError(
      `SchemaID "${schemaId}" não suportado. Esperado "D0".`,
    );
  }

  // Regra 3: JoinEUI — exatamente 16 hex
  if (!isValidHex(joinEUI, 16)) {
    throw new Tr005ParseError(
      'JoinEUI inválido. Deve conter 16 caracteres hexadecimais.',
    );
  }

  // Regra 4: DevEUI — exatamente 16 hex
  if (!isValidHex(devEUI, 16)) {
    throw new Tr005ParseError(
      'DevEUI inválido. Deve conter 16 caracteres hexadecimais.',
    );
  }

  // Regra 5: ProfileID — opcional; quando ausente usa default,
  // quando presente deve ser exatamente 8 hex.
  let profileId = DEFAULT_PROFILE_ID;
  if (profileIdRaw !== undefined && profileIdRaw !== '') {
    if (!isValidHex(profileIdRaw, 8)) {
      throw new Tr005ParseError(
        'ProfileID inválido. Deve conter 8 caracteres hexadecimais.',
      );
    }
    profileId = profileIdRaw;
  }

  // Regra 6: extensões após ProfileID já foram ignoradas no split acima.
  return { schemaId, joinEUI, devEUI, profileId };
}

/**
 * Gera uma AppKey aleatória de 32 caracteres hexadecimais.
 *
 * Usa crypto.getRandomValues se disponível (browser moderno),
 * fallback para Math.random (ambiente de teste).
 *
 * @returns AppKey em uppercase (ex: "A1B2C3D4E5F6...")
 */
export function generateAppKey(): string {
  let result = '';

  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    result = Array.from(bytes)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('')
      .toUpperCase();
  } else {
    // Fallback NÃO criptográfico: apenas para ambientes sem Web Crypto
    // (jsdom/Node antigo, testes). Em produção o browser sempre expõe
    // crypto.getRandomValues; esta ramificação não gera chave segura.
    for (let i = 0; i < 32; i++) {
      result += HEX_CHARS[Math.floor(Math.random() * 16)];
    }
  }

  return result;
}

/**
 * Verifica se uma string parece ser um QR TR005 válido (sem lançar exceção).
 * Útil para validação em formulários.
 */
export function isValidTr005(text: string): boolean {
  try {
    parseTr005(text);
    return true;
  } catch {
    return false;
  }
}
