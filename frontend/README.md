# Frontend - React + TypeScript + Tailwind CSS

Este projeto foi inicializado utilizando o **Vite** para um ambiente de desenvolvimento rápido e moderno, configurado com **TypeScript**, **Tailwind CSS**, **MSW** para mocking de contratos de API e padronização automatizada de código com **OxLint**, **Prettier** e **Husky**.

---

## 🛠️ Tecnologias e Ferramentas Utilizadas

* **[Vite](https://vitejs.dev/)**: Build tool e servidor de desenvolvimento ultrarrápido.
* **[React](https://react.dev/)**: Biblioteca para construção de interfaces de usuário.
* **[TypeScript](https://www.typescriptlang.org/)**: Superset do JavaScript com tipagem estática.
* **[Tailwind CSS](https://tailwindcss.com/)**: Framework CSS utility-first para estilização rápida e responsiva.
* **[Axios](https://axios-http.com/)**: Cliente HTTP centralizado com suporte a interceptors de autenticação (JWT) e tratamento global de erros (401).
* **[React Router](https://reactrouter.com/)**: Roteamento dinâmico SPA, suporte a `lazy loading` de páginas e agrupamento de rotas protegidas sob o layout principal.
* **[React Hook Form](https://react-hook-form.com/) & [Zod](https://zod.dev/)**: Gerenciamento de formulários com validações estritamente tipadas baseadas em schemas.
* **[MSW (Mock Service Worker)](https://mswjs.io/)**: Interceptação de requisições HTTP locais via Service Worker para mocking de APIs baseado no contrato OpenAPI.
* **[OpenAPI / Redocly](https://redocly.com/)**: Especificação do contrato da API REST (`openapi-stub.yaml`) e linter para validação dos schemas.
* **[OxLint](https://oxc.rs/) & [Prettier](https://prettier.io/)**: Análise estática ultrarrápida e formatador de código para manutenção da qualidade visual e lógica.
* **[Husky](https://typicode.github.io/husky/) & [Lint-staged](https://github.com/lint-staged/lint-staged)**: Automação de hooks do Git para validação de linting e formatação antes dos commits.
* **[GitHub Actions](https://github.com/features/actions)**: Pipeline de CI (`.github/workflows/frontend-ci.yml`) para validação automatizada de contrato OpenAPI, linting, checagem de tipos com TypeScript e build.

---

## 📁 Estrutura do Projeto

Abaixo está a organização atualizada da raiz e do diretório `frontend/`:

```text
.
├── .github/
│   └── workflows/
│       └── frontend-ci.yml   # Pipeline de CI/CD (GitHub Actions)
└── frontend/
    ├── .husky/               # Hooks do Git configurados pelo Husky
    ├── public/
    │   └── mockServiceWorker.js # Service Worker estático gerado pelo MSW
    ├── src/
    │   ├── assets/           # Imagens, ícones e recursos estáticos
    │   ├── components/       # Componentes genéricos e de layout (Layout, Spinner, etc.)
    │   ├── contexts/         # Contextos globais do React (ex: AuthContext)
    │   ├── hooks/            # Custom React Hooks
    │   ├── mocks/            # Configurações e handlers do MSW para desenvolvimento local
    │   │   ├── browser.ts
    │   │   └── handlers.ts
    │   ├── pages/            # Páginas/Rotas da aplicação
    │   │   ├── app/
    │   │   │   └── NewApp.tsx # Tela de cadastro de Aplicação
    │   │   ├── tenants/
    │   │   │   └── NewTenant.tsx # Tela de cadastro de Tenant
    │   │   ├── AppDetail.tsx
    │   │   ├── Dashboard.tsx
    │   │   ├── Devices.tsx
    │   │   ├── Login.tsx
    │   │   ├── NotFound.tsx
    │   │   └── Tenants.tsx   # Listagem e associação de Tenants/Aplicações
    │   ├── services/         # Instância centralizada do Axios e serviços de API
    │   │   ├── api.ts        # Cliente Axios base com Interceptors
    │   │   ├── app.ts        # Métodos de integração do módulo de Aplicações
    │   │   └── tenant.ts     # Métodos de integração do módulo de Tenant
    │   ├── types/            # Definições de tipos e interfaces TypeScript
    │   ├── App.tsx           # Componente principal de entrada da interface
    │   ├── routes.tsx        # Definição e agrupamento de rotas (AppRoutes)
    │   ├── index.css         # Estilos globais e diretivas do Tailwind CSS
    │   └── main.tsx          # Ponto de entrada do React e ativador do MSW em Dev
    ├── .env                  # Variáveis de ambiente locais (não versionado)
    ├── .env.example          # Modelo das variáveis de ambiente
    ├── .oxlintrc.json        # Configuração do OxLint
    ├── .prettierrc           # Regras de formatação do Prettier
    ├── index.html            # Documento HTML principal
    ├── openapi-stub.yaml     # Contrato OpenAPI 3.0 (Source of Truth da API REST)
    ├── package.json          # Dependências e scripts do projeto
    ├── postcss.config.js     # Processamento do Tailwind CSS
    ├── tailwind.config.js    # Configuração de temas e plugins do Tailwind
    └── vite.config.ts        # Configuração do Vite
