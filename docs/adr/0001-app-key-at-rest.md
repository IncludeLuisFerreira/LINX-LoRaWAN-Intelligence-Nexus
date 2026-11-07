# ADR 0001 — `app_key` em repouso

- **Status:** Aceito
- **Data:** 2026-11-07
- **Contexto da issue:** #218 (item 3), implementação rastreada em #85
- **Decisores:** equipe LINX

## Contexto

O `identity_api` armazena a chave OTAA `app_key` do dispositivo LoRaWAN em
texto puro no Postgres (`devices.app_key`, `VARCHAR(32)`). A chave não é
exposta nas respostas da API, mas vaza em dumps, backups e acesso direto ao
banco. O `app_key` é usado para provisionar o dispositivo no ChirpStack no
momento da criação.

A issue #218 pede uma decisão explícita entre criptografia de coluna e cofre
externo antes de implementar. A implementação não faz parte da #218 e deve
ocorrer na #85 para evitar duas soluções concorrentes.

## Opções consideradas

1. **Criptografia de coluna com AES-256-GCM no `identity_api`.**
   - Chave mestra em secret de ambiente (`APP_KEY_ENCRYPTION_KEY`), com
     rotação documentada.
   - Nonce aleatório de 12 bytes por operação; blob = nonce + ciphertext + tag.
   - Simples de operar, sem dependência de rede no caminho de criação do
     dispositivo.
   - Exige migração/backfill e cuidado para não logar plaintext.

2. **Cofre externo (AWS Secrets Manager/Vault).**
   - Elimina a chave do banco, mas adiciona dependência de rede, custo e
     latência no caminho de provisionamento.
   - Melhor quando já existe um cofre operado e política de rotação
     centralizada.

3. **Manter texto puro e restringir acesso ao banco.**
   - Não atende ao requisito: dump/backup continua expondo a chave.

## Decisão

Adotar **AES-256-GCM em nível de aplicação** na #85:

- Chave mestra de 32 bytes em `APP_KEY_ENCRYPTION_KEY`, fornecida por secret
  do ambiente (nunca no repositório).
- Nonce de 12 bytes por operação; formato armazenado inclui versão do
  algoritmo, nonce e ciphertext/tag.
- `Device.app_key` passa a armazenar o blob criptografado (tipo binário ou
  texto base64 com prefixo de versão).
- Escrita criptografa antes do `commit`; leitura descriptografa apenas no
  caminho que precisa enviar a chave ao ChirpStack.
- Respostas da API continuam sem `app_key`.
- Rotação: nova chave mestra aceita para leitura durante uma janela de
  migração; reencriptar os registros e remover a chave antiga depois.

## Consequências

- Dump/backup do Postgres deixa de expor o `app_key` em claro.
- O serviço precisa da chave mestra no startup; ausência deve falhar de forma
  explícita, como os demais segredos obrigatórios.
- A migração precisa de backfill dos dispositivos existentes e de um teste
  round-trip encrypt/decrypt.
- Perda da chave mestra torna as chaves existentes irrecuperáveis; o
  procedimento de backup/rotação da chave deve ser documentado no runbook.
- O cofre externo permanece uma opção futura se a operação exigir rotação
  centralizada; a interface de criptografia deve permitir trocar o backend.

## Implementação

Rastreada na issue **#85** (`feat(backend): encrypt app_key at rest
(AES-256-GCM)`). Critérios de aceite da #85 permanecem válidos; a #218 apenas
registra esta decisão.
