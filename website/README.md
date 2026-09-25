# LINX — Website

Site institucional da **LINX (LoRaWAN Intelligence Nexus)**, plataforma SaaS IoT
gerenciada. O site comunica quatro impressões centrais: **segurança, IoT,
tecnologia e facilidade**.

- **Stack:** [Astro](https://docs.astro.build) 7 + CSS puro + JavaScript vanilla.
- **3D:** [`three.js`](https://threejs.org) apenas no hero (carregado
  dinamicamente).
- **Sem framework de UI.** Interatividade com `IntersectionObserver` e eventos
  nativos.

> O contrato de marca (cores, tipografia, movimento) fica em
> [`DESIGN.md`](./DESIGN.md) e nos tokens de
> [`src/styles/global.css`](./src/styles/global.css). **Leia o `DESIGN.md` antes
> de mudar o visual.**

---

## Como rodar

Requer Node `>=22.12.0`.

```bash
npm install
npm run dev      # servidor de desenvolvimento (http://localhost:4321)

# No dia a dia deste repositório, use o modo background:
npx astro dev --background
npx astro dev status
npx astro dev logs
npx astro dev stop

npm run build    # build de produção em ./dist
npm run preview  # pré-visualiza o build
```

---

## Estrutura

```
website/
├── DESIGN.md                     # contrato de marca (OpenDesign)
├── public/                       # estáticos servidos na raiz (favicon)
├── src/
│   ├── layouts/
│   │   └── Layout.astro          # <head>, fontes, CSS global e script de movimento
│   ├── pages/
│   │   ├── index.astro           # home (one-page) — compõe as seções
│   │   └── about.astro           # página "Sobre"
│   ├── components/
│   │   ├── Header.astro          # nav sticky + Entrar/Criar conta + drawer mobile
│   │   ├── Hero.astro            # proposta de valor + cena three.js
│   │   ├── SocialProof.astro     # clientes + métricas com contador
│   │   ├── Features.astro        # grade bento de recursos
│   │   ├── HowItWorks.astro      # 3 passos
│   │   ├── Security.astro        # segurança + exemplo de requisição
│   │   ├── UseCases.astro        # casos de uso (agro/indústria/logística)
│   │   ├── Contact.astro         # CTA final + formulário de e-mail
│   │   └── Footer.astro          # rodapé
│   └── styles/
│       └── global.css            # tokens, reset, utilitários, botões, movimento
└── docs/superpowers/             # specs e planos anteriores (histórico)
```

### Ordem das seções

Definida em [`src/pages/index.astro`](./src/pages/index.astro):
`Header → Hero → SocialProof → Features → HowItWorks → Security → UseCases →
Contact → Footer`.

---

## Como modificar

### Trocar cores e tipografia

Edite os tokens em `src/styles/global.css` (`:root`) e replique a decisão no
`DESIGN.md`. Os componentes usam **apenas** variáveis (`var(--color-…)`), então
a mudança se propaga pelo site inteiro. **Nunca** use cor literal em componente.

### Trocar/ajustar conteúdo

A maioria dos textos de lista vive no *frontmatter* (bloco `---`) de cada
componente, como arrays. Regras práticas:

- **Header**: itens de menu em `navItems`.
- **SocialProof**: clientes em `customers`, métricas em `metrics`. Para o
  contador, o `<strong>` usa `data-count`, `data-decimals` e `data-suffix`.
- **Features**: cards em `features` (`size`: `big` | `half` | `sm`; `accent`
  pinta o card de teal; `icon` referencia o objeto `icons`).
- **HowItWorks**: passos em `steps`.
- **Security**: tópicos em `points`.
- **UseCases**: cards em `cases`.
- **Footer**: colunas em `columns`, links legais em `legalLinks`, redes em
  `socials`.

### Adicionar uma seção

1. Crie `src/components/MinhaSecao.astro` seguindo um componente existente
   (frontmatter + `<style>` com escopo local).
2. Use as classes utilitárias globais (`container`, `section`, `section--alt`,
   `eyebrow`, `section__title`, `card`, `btn btn--primary`…).
3. Importe e insira em `src/pages/index.astro` na ordem desejada.
4. Dê um `id` à seção e, se quiser link no menu, adicione o item em
   `navItems` no `Header.astro`.

### Imagens

As imagens dos casos de uso são **placeholders** (`picsum.photos`) e devem ser
trocadas por fotos próprias. Coloque os arquivos em `public/` e referencie com
caminho absoluto (`/minha-foto.jpg`), mantendo `loading="lazy"` e
`width`/`height`.

---

## Movimento

O comportamento é controlado por atributos de dados:

| Atributo | Efeito | Onde é tratado |
| --- | --- | --- |
| `data-reveal` | Entra em cascata quando aparece na tela. Atraso opcional via `--reveal-delay`. | Script em `Layout.astro` |
| `data-count` (+ `data-decimals`, `data-suffix`) | Contador animado ao entrar na tela. | Script em `Layout.astro` |
| `data-tilt` | Tilt 3D + spotlight que segue o cursor. | Script em `Layout.astro` |
| `#hero-canvas` | Cena 3D (malha viva). | Script em `Hero.astro` |

- A cena do hero usa uma **esfera uniforme (Fibonacci)** de nós + nuvem central
  e pulsos de dados. Ajuste quantidade de nós, raio e velocidade no script de
  `Hero.astro`.
- Tudo é desligado com `prefers-reduced-motion: reduce`; a cena pausa quando
  fora da tela ou com a aba oculta e reduz nós no mobile.

---

## Acessibilidade

- HTML semântico, `skip-link` ("Pular para o conteúdo"), foco visível.
- Contraste AA; o card de destaque (teal) usa **texto branco**.
- Botões de ícone com `aria-label`; formulários com `<label>`.
- Ao adicionar interatividade, preserve navegação por teclado (`Escape` fecha o
  drawer no `Header.astro`).

---

## Autenticação (Auth0)

O login usa **OAuth2/OIDC com Authorization Code + PKCE** em `/api/auth/*`:

- `GET /api/auth/login` — inicia o fluxo (aceita `screen_hint` e `login_hint`).
- `GET /api/auth/callback` — valida `state`/`nonce`, troca o code e cria a sessão.
- `GET /api/auth/me` — retorna o usuário da sessão (ou `401`).
- `POST /api/auth/logout` — limpa a sessão e encerra no Auth0.

A sessão fica num cookie `linx_session` **httpOnly, SameSite=Lax e cifrado**
(JWE via `jose`). O cookie é **host-only**: pertence apenas ao domínio do
website e **não é compartilhado com o app da plataforma**. Por isso o callback
redireciona para `POST_LOGIN_REDIRECT` (same-origin) e não para o app.

> Integração de SSO entre website e app é trabalho futuro. O app atual usa
> autenticação própria e não lê este cookie.

As proteções de CSRF das rotas sob demanda usam o `security.checkOrigin` do
Astro, habilitado explicitamente em `astro.config.mjs`.

Testes: `npm run test:run` (Vitest, alias de `astro:env/server` em
`src/test/env.ts`).

---

## Pendências / backend

- **Formulário de contato** (`Contact.astro`) faz `POST /api/subscribe`, que
  **ainda não existe**. Implementar endpoint no backend ou trocar por outro
  destino.
- Métricas e textos são **placeholder plausível** — substituir por dados reais.

---

## Deploy

O serviço já possui `Dockerfile` e `nginx.conf` (ver histórico do repositório e
`deploy/`). O build gera `dist/` estático; o nginx serve os arquivos e aplica
cache/headers.
