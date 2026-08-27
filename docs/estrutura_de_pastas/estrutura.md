# Estrutura de Pastas - Projeto LINX (Cloud)

Este documento resume a estrutura principal (primeiro nível) do repositório do projeto LINX e o objetivo de cada diretório.

| Diretório / Pasta | Objetivo Principal |
| :--- | :--- |
| **`saas_backend/`** | É o cérebro central (Core) da plataforma. Responsável por gerenciar Organizações, Aplicações e Usuários. Também faz a integração principal com a rede LoRaWAN (ChirpStack/MQTT) e orquestra a criação automática dos contêineres para novos clientes. |
| **`client_agent_api/`** | Atua como **Middleware** de segurança e roteamento. Intercepta todas as requisições (do Frontend ou de integrações externas), valida as permissões do usuário e repassa os comandos para o contêiner isolado correto da aplicação solicitada. |
| **`tenant_app_template/`** | É o **molde (template)** do ambiente isolado de cada cliente. Contém o motor de regras, os scripts de acionamento e a estrutura do banco de dados (TimescaleDB). Quando uma nova aplicação é criada, este diretório dita como o contêiner daquele cliente deve ser construído na nuvem. |
| **`frontend/`** | Aplicação web centralizada (Dashboard/Interface). Contém todo o código visual (HTML/CSS/JS) da plataforma. Renderiza os painéis dinamicamente consumindo os dados da `client_agent_api`, dependendo de qual aplicação o usuário acessou. |
| **`infra/`** | Contém a orquestração da **infraestrutura base** compartilhada. Aqui ficam os arquivos do Docker Compose e configurações de serviços que sustentam a nuvem, como o próprio ChirpStack (LoRaWAN Network Server), o Broker MQTT e o banco de dados SaaS principal. |