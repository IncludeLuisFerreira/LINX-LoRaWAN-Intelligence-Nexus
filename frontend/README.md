# Frontend - React + TypeScript + Tailwind CSS

Este projeto foi inicializado utilizando o **Vite** para um ambiente de desenvolvimento rápido e moderno, configurado com **TypeScript**, **Tailwind CSS**, e padronização de código automatizada de alta performance com **OxLint**, **Prettier** e **Husky**.

---

## 🛠️ Tecnologias e Ferramentas Utilizadas

* **[Vite](https://vitejs.dev/)**: Build tool e servidor de desenvolvimento ultrarrápido.
* **[React](https://react.dev/)**: Biblioteca para construção de interfaces de usuário.
* **[TypeScript](https://www.typescriptlang.org/)**: Superset do JavaScript que adiciona tipagem estática ao código.
* **[Tailwind CSS](https://tailwindcss.com/)**: Framework CSS utility-first para estilização rápida e responsiva.
* **[PostCSS](https://postcss.org/) & [Autoprefixer](https://github.com/postcss/autoprefixer)**: Ferramentas para processamento e compatibilidade de CSS entre navegadores.
* **[OxLint](https://oxc.rs/)**: Linter ultrarrápido em Rust para análise estática e prevenção de erros.
* **[Prettier](https://prettier.io/)**: Formatador de código opinativo para manter um estilo visual consistente.
* **[Husky](https://typicode.github.io/husky/) & [Lint-staged](https://github.com/lint-staged/lint-staged)**: Automação de hooks do Git para garantir validação de linting e formatação antes dos commits.

---

## 📁 Estrutura do Projeto

Abaixo está a organização de arquivos da raiz e a estrutura interna recomendada para o diretório `src/`:

```text
frontend/
├── .husky/              # Hooks do Git configurados pelo Husky
├── src/
│   ├── assets/          # Imagens, ícones e arquivos estáticos importáveis
│   ├── components/      # Componentes reutilizáveis (botões, inputs, modais)
│   ├── contexts/        # Contextos do React para gerenciamento de estado global
│   ├── hooks/           # Custom React Hooks
│   ├── pages/           # Páginas/Rotas da aplicação
│   ├── services/        # Integrações com APIs externas e serviços
│   ├── types/           # Definições de tipos e interfaces do TypeScript
│   ├── App.tsx          # Componente principal da aplicação
│   ├── index.css        # Estilos globais e diretivas do Tailwind CSS
│   └── main.tsx         # Ponto de entrada do React
├── .oxlintrc.json       # Configuração do OxLint
├── .prettierrc          # Regras de formatação do Prettier
├── index.html           # Documento HTML principal
├── package.json         # Dependências, scripts e configurações do lint-staged
├── postcss.config.js    # Processamento do Tailwind CSS
├── tailwind.config.js   # Configuração de temas e conteúdos do Tailwind
└── vite.config.ts       # Configuração das compilações do Vite