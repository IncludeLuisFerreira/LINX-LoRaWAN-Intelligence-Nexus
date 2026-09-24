# LINX — Brand Contract (DESIGN.md)

> Contrato de marca no formato do OpenDesign. Toda interface do site LINX deve respeitar as decisões abaixo. Alterações aqui refletem em `src/styles/global.css`.

## Posicionamento

**Produto:** LINX — LoRaWAN Intelligence Nexus. Plataforma SaaS IoT gerenciada para aquisição, processamento e visualização de telemetria de sensores LoRaWAN.

**Impressão que o site deve causar:** segurança, IoT, tecnologia e **facilidade**.

**Mensagem central:** "Sensores conectados. Infraestrutura zero." — o cliente não instala gateways nem mantém servidores; conectividade LoRaWAN é provida como serviço e o provisionamento é plug and play por QR Code.

**Evitar:** posicionamento genérico de "plataforma para devs"; jargão de deploy/CI; promessas de nuvem sem relação com IoT.

## Princípios visuais

- **Clareza acima de ornamento.** Muito espaço em branco, hierarquia forte, texto direto.
- **Um único acento** (teal). Sem gradientes roxo/azul "de IA", sem múltiplos acentos competindo.
- **Profundidade por superfície, não por sombra pesada.** Sombras tingidas de azul, rings finos.
- **Movimento com propósito.** A malha viva de nós comunica IoT; reveals comunicam estrutura. Respeitar `prefers-reduced-motion`.
- **Técnico, mas acolhedor.** Monoespaçada para dados/IDs; prosa curta e ativa para o resto.

## Paleta

| Papel | Token | Valor |
| --- | --- | --- |
| Tinta / texto | `--color-text` | `#0b1f33` |
| Fundo | `--color-bg` | `#ffffff` |
| Fundo alternado | `--color-bg-alt` | `#f4f8fb` |
| Texto secundário | `--color-text-secondary` | `#5b6b7c` |
| Texto discreto | `--color-text-muted` | `#8a97a5` |
| Borda | `--color-border` | `#e2e8f0` |
| **Acento (único)** | `--color-accent` | `#0d9488` |
| Acento hover | `--color-accent-strong` | `#0f766e` |
| Acento soft | `--color-accent-soft` | `rgba(13,148,136,.10)` |
| Superfície escura | `--color-primary` | `#0b1f33` |
| Sucesso | `--color-success` | `#16a34a` |
| Alerta | `--color-warn` | `#d97706` |
| Erro | `--color-danger` | `#dc2626` |

## Tipografia

- **Display/corpo:** `Geist` (fallback `Inter, system-ui, sans-serif`).
- **Dados/código/IDs:** `Geist Mono` (`ui-monospace, monospace`).
- Títulos com tracking negativo; `text-wrap: balance` em headlines; `tabular-nums` em métricas.
- Pesos: 400 corpo, 500 ênfase, 600/700 labels e títulos de seção, 800 display.

## Espaçamento e forma

- Ritmo base de 4px. Seções com `clamp(3rem, 8vw, 6rem)`.
- Container `1200px`. Raio: 8px controles, 12px cards, 16px seções.
- Sombras: `0 10px 30px rgba(11,31,51,.06)`; foco `0 0 0 3px var(--color-accent-soft)`.

## Movimento

- **Hero:** cena `three.js` com malha de nós em esfera uniforme (distribuição Fibonacci), pulsos de dados nas arestas, nuvem no centro, parallax de mouse e rotação lenta.
- **Scroll:** reveals em cascata (IntersectionObserver + CSS), contadores animados.
- **Micro-interações:** hover/press em botões, tilt + spotlight em cards, link ativo na nav.
- **Fallbacks:** `prefers-reduced-motion` desliga 3D e reveals; cena pausa quando fora da tela/aba oculta; contagem de nós reduzida no mobile.

## Acessibilidade

- HTML semântico, foco visível, contraste AA, `skip-link`, labels em formulários, `aria-*` em controles interativos.
- Nunca depender só de cor para estado.
