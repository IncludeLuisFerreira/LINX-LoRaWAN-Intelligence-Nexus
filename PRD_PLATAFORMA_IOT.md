# Documento de Definição do Produto (PRD)

**Nome do Produto:** LINX - LoRaWAN Intelligence Nexus
**Versão:** 1.0 (Cloud-Native & App-Isolated Architecture)
**Status:** Documento de definição do produto
**Tipo:** Plataforma SaaS IoT Distribuída
**Contexto:** Projeto acadêmico de Sistemas Distribuídos com potencial de evolução para produto de startup
**Infraestrutura-alvo:** AWS (100% Nuvem)
**Arquitetura:** Distribuída, orientada a serviços, comunicação assíncrona e orquestração de contêineres dedicados por aplicação.

---

## 1. Visão Geral

### 1.1. Descrição do produto

A Plataforma IoT Distribuída LINX é uma solução para aquisição, processamento, gerenciamento e visualização de dados provenientes de dispositivos IoT (LoRaWAN). O foco central do produto é a simplicidade de implantação (*plug and play*) associada a uma arquitetura distribuída altamente escalável baseada em nuvem.

A conectividade LoRaWAN é fornecida por uma **rede externa de Gateways** operada pela própria startup. Assim, o cliente não precisa adquirir, instalar, configurar ou manter Gateways no seu ambiente: o hardware no local se limita aos sensores/dispositivos finais (e, quando aplicável, suas fontes de energia e fixação). O SaaS realiza o onboarding dos sensores e faz o roteamento/armazenamento/acionamento na nuvem, enquanto a camada de rádio é provida como serviço pela rede de cobertura.

A plataforma adota um modelo arquitetural de **isolamento por aplicação**. A infraestrutura central em nuvem (SaaS Backend) atua como orquestradora geral e roteadora de comunicação. Para cada Aplicação criada por uma Organização, o sistema provisiona um ambiente isolado (contêineres Docker) também na nuvem, contendo o motor de regras, armazenamento de telemetria (PostgreSQL/TimescaleDB) e serviços específicos daquela aplicação. O ambiente físico (Edge) é restrito exclusivamente aos sensores e Gateways de comunicação de rádio (RF).

### 1.2. Problema

As soluções IoT B2B frequentemente exigem configurações complexas de infraestrutura mista (nuvem + servidores físicos no cliente), dificultando a escalabilidade, encarecendo a manutenção e aumentando os riscos de segurança.
Existe a oportunidade para uma solução "Zero-Infra Local", que centralize todo o processamento de regras, acionamentos e telemetria na nuvem, mantendo a flexibilidade de projetos isolados por cliente.

### 1.3. Proposta de valor

A plataforma oferece:

- **Abordagem 100% Plug and Play:** O cliente apenas cadastra sensores via QR Code. A conectividade é provida pela rede externa de Gateways da startup e o provisionamento da infraestrutura lógica na nuvem é automático.
- **Isolamento por Aplicação (Tenant-Isolation):** Regras de negócio e persistência de dados de cada aplicação rodam em contêineres dedicados na nuvem, garantindo segurança, privacidade e performance previsível.
- **Zero Manutenção de Servidores Locais:** Remoção completa da necessidade de manter banco de dados, motores de regras ou orquestração em servidores físicos no ambiente do cliente.

---

## 2. Objetivos do Produto

### 2.1. Objetivo geral

Desenvolver uma plataforma IoT distribuída em nuvem capaz de conectar dispositivos LoRaWAN, processar telemetria, executar acionamentos e gerenciar recursos de forma hierárquica (Organização → Aplicação → Dispositivo) utilizando orquestração de contêineres isolados.

### 2.2. Objetivos específicos

| Objetivo | Descrição |
| --- | --- |
| **Conectividade** | Integrar dispositivos IoT à nuvem via Gateways LoRaWAN e protocolo MQTT. |
| **Orquestração Multi-Tenant** | Provisionar ambientes Docker isolados para cada Aplicação cadastrada. |
| **Gerenciamento Facilitado** | Permitir o cadastro ágil de dispositivos via leitura de QR Code (Padrão TR005). |
| **Processamento e Acionamento** | Executar regras de negócio e acionamentos (Downlinks) na nuvem. |
| **Tempo Real** | Disponibilizar telemetria para o dashboard via WebSocket. |
| **Segurança** | Garantir autenticação, autorização (RBAC) e comunicação TLS. |

---

## 3. Público-Alvo

### 3.1. Clientes

Organizações B2B que demandam monitoramento IoT em diferentes projetos/aplicações, mas não desejam manter infraestrutura de TI local:

- Agricultura de precisão (monitoramento de silos, estufas);
- Indústria e automação;
- Logística e infraestrutura;
- Empresas integradoras de IoT.

### 3.2. Usuários

| Perfil | Necessidade |
| --- | --- |
| **Administrador da Organização** | Criar aplicações, gerenciar usuários globais e faturamento. |
| **Operador/Gestor da Aplicação** | Monitorar dashboards, definir regras de negócio e acionamentos de um projeto específico. |
| **Técnico de Campo** | Instalar Gateways, ler QR Codes de sensores e vinculá-los às aplicações. |
| **Administrador SaaS** | Gerenciar infraestrutura AWS e manter a disponibilidade global. |

---

## 4. Casos de Uso

**UC01 — Cadastro de Organização e Criação de Aplicação**

- **Atores:** Administrador da Plataforma, SaaS Backend.
- **Fluxo Principal:** O administrador cadastra uma organização no SaaS e cria uma nova "Aplicação" no painel SaaS. Uma “aplicação” precisa estar relacionada à uma organização. O SaaS Backend orquestra na nuvem um novo *Docker Cliente* isolado para este projeto (contendo exclusivamente os bancos de dados PostgreSQL/TimescaleDB e o motor de regras da aplicação). O SaaS Backend atualiza as rotas da **Client Agent API** (middleware) para que ela saiba direcionar requisições futuras para esta nova instância isolada.

**UC02 — Gestão de Usuários e Controle de Acesso (RBAC)**

- **Atores:** Administrador da Organização, Aplicação, SaaS Backend, Client Agent API.
- **Fluxo Principal:** O administrador convida um usuário e o vincula a uma Aplicação. O SaaS Backend registra as permissões. Ao fazer login, o usuário recebe um token JWT. Todas as requisições desse usuário passarão pela **Client Agent API**, que atuará como middleware de segurança, validando o token e garantindo que ele só acesse os recursos do *Docker Cliente* da sua aplicação autorizada.

### Categoria B: Infraestrutura IoT e Conectividade

**UC03 — Cadastro de Gateway LoRaWAN**

- **Atores:** Administrador SaaS, Equipe de Operação de Rede (Startup), SaaS Backend, ChirpStack.
- **Fluxo Principal:** A startup opera uma rede externa de Gateways LoRaWAN (infraestrutura própria) e é responsável por planejar cobertura, instalar, cadastrar e monitorar os Gateways na região atendida. Os Gateways são previamente provisionados pela startup e vinculados ao ambiente ChirpStack (AWS), de modo que os sensores dos clientes possam utilizar a cobertura existente sem que o cliente instale hardware de gateway no local. O SaaS Backend utiliza o ChirpStack como camada de rede LoRaWAN e mantém a lógica de roteamento (Organização → Aplicação → Dispositivo) e persistência em nuvem.
- **Pós-condição:** A rede de Gateways está operacional e apta a receber uplinks dos sensores, encaminhando-os ao ChirpStack/MQTT para posterior roteamento e persistência na nuvem.

**UC04 — Provisionamento de Sensor via QR Code (TR005)**

- **Atores:** Técnico de Campo, SaaS Backend, ChirpStack, Client Agent API.
- **Fluxo Principal:** O técnico escaneia o QR Code do sensor pelo celular ou do computador e o vincula a uma Aplicação. O SaaS Backend provisiona o dispositivo no ChirpStack (via gRPC). A partir desse momento, a **Client Agent API** é instruída a rotear toda a telemetria proveniente deste sensor diretamente para o banco de dados isolado da aplicação escolhida.

**UC05 — Atualização Remota de Firmware (FUOTA)**

- **Atores:** Administrador, Client Agent API, SaaS Backend, ChirpStack.
- **Fluxo Principal:** O administrador agenda uma atualização de firmware pelo painel. A requisição bate na **Client Agent API** (middleware), que autentica a chamada e repassa o comando ao SaaS Backend. O SaaS Backend coordena com o ChirpStack o envio do arquivo em pacotes *multicast* (Downlink) para os sensores físicos.

## Categoria C: Operação, Regras e Monitoramento (Nuvem)

**UC06 — Monitoramento de Telemetria em Tempo Real**

- **Atores:** Operador, SaaS Backend, Client Agent API, Frontend.
- **Fluxo Principal:** O operador acessa o dashboard. O frontend abre uma conexão WebSocket. O sensor transmite um dado que chega ao MQTT via ChirpStack. O SaaS Backend lê a fila MQTT e repassa à **Client Agent API**. O middleware salva o dado no *TimescaleDB* isolado da aplicação e, simultaneamente, faz o *push* via WebSocket para o frontend do operador.

**UC07 — Configuração de Regras de Negócio e Acionamento Remoto (Downlink)**

- **Atores:** Operador, Docker Cliente (Motor de Regras), Client Agent API, SaaS Backend.
- **Fluxo Principal:** O operador cadastra uma regra ("Temperatura > 40ºC liga o exaustor"). Essa regra fica salva no *Docker Cliente* da aplicação. Quando a telemetria chega, o motor isolado confirma a violação da regra e gera um comando de acionamento. Esse comando sobe para a **Client Agent API**, que o encaminha ao SaaS Backend, que por sua vez aciona o ChirpStack via gRPC para transmitir o *Downlink* até o Gateway físico.

**UC08 — Disparo de Alertas (Telegram/Email)**

- **Atores:** Docker Cliente (Motor de Regras), Client Agent API, Serviço de Notificação.
- **Fluxo Principal:** O motor de regras da aplicação (no Docker isolado) detecta uma anomalia nos dados recém-chegados. Ele dispara um evento de alerta para a **Client Agent API**. O middleware intercepta o evento, formata a mensagem e invoca a API externa (Telegram ou Email) para notificar a equipe configurada naquela aplicação.

**UC09 — Consulta de Histórico e Integração Externa (APIs REST)**

- **Atores:** Sistema Externo (ERP do Cliente), Client Agent API, Docker Cliente.
- **Fluxo Principal:** O ERP do cliente solicita o histórico de dados de um mês enviando uma requisição HTTP/REST. A **Client Agent API** atua como *API Gateway/Middleware*, valida o token de acesso (TLS/HTTPS) e roteia a consulta para o PostgreSQL/TimescaleDB isolado daquela aplicação. Os dados são recuperados, formatados em JSON pelo middleware e devolvidos ao ERP.

---

## 5. Requisitos Funcionais

### 5.1. Gestão de Organizações e Aplicações

- **RF-001:** O sistema deve permitir o cadastro de organizações (Tenants).
- **RF-002:** O sistema deve permitir que uma organização crie e gerencie múltiplas Aplicações.
- **RF-003:** O sistema deve garantir que usuários tenham papéis (RBAC) aplicáveis no nível da organização ou restritos a aplicações específicas.

### 5.2. Orquestração e Isolamento em Nuvem (Tenant-Isolated)

- **RF-010:** Para cada Aplicação criada, a plataforma deve provisionar um ambiente "Docker Cliente" dedicado na nuvem.
- **RF-011:** A lógica de negócio  e confirmação de regras  devem rodar exclusivamente neste contêiner isolado.
- **RF-012:** Cada Aplicação deve possuir persistência de dados isolada (PostgreSQL + TimescaleDB próprio na nuvem).
- **RF-013:** O SaaS Backend deve rotear os dados (via MQTT/gRPC) garantindo que a telemetria de um dispositivo chegue apenas ao contêiner da sua respectiva aplicação.

### 5.3. Gestão e Ingestão de Dispositivos (IoT)

- **RF-020:** Dispositivos devem ser obrigatoriamente vinculados a uma Aplicação.
- **RF-021:** O sistema deve suportar o provisionamento *plug and play* lendo o QR Code (TR005) com *SchemaID, JoinEUI, DevEUI*, etc ou solicitando o usuário preencher manualmente esses dados.
- **RF-022:** O SaaS Backend deve intermediar a criação e gerenciamento do dispositivo no motor LoRaWAN (ChirpStack v4).
- **RF-023:** O sistema deve permitir atualizações remotas de firmware em lote (FUOTA).

### 5.4. Comunicação em Tempo Real

- **RF-030:** O sistema deve prover endpoints de WebSocket autenticados para telemetria em tempo real no dashboard.
- **RF-031:** O sistema deve detectar desconexões no Frontend e tentar reconexão automática, recuperando histórico perdido (REST) do banco da aplicação.

### 5.5. Requisitos de Sistemas Distribuídos (Coordenação e Tolerância a Falhas)

- **RF-040 (Nomeação):** Todo recurso (Organização, Aplicação, Dispositivo, Serviço) deve possuir um identificador único (UUID/URN) para navegação no sistema distribuído.
- **RF-041 (Consistência):** O sistema deve definir o tratamento para mensagens MQTT duplicadas ou fora de ordem utilizando *timestamps* do Gateway e *relógios lógicos*.
- **RF-042 (Resiliência):** O SaaS Backend deve implementar políticas de *retry* com *backoff* exponencial para falhas de comunicação gRPC/REST com os contêineres das aplicações.

---

## 6. Requisitos Não Funcionais

- **RNF-001 (Escalabilidade):** A arquitetura deve suportar aumento horizontal da infraestrutura, tanto no cluster do SaaS Backend quanto na orquestração de milhares de instâncias "Docker Cliente".
- **RNF-002 (Disponibilidade):** Os serviços core da plataforma devem ter meta de *uptime* ≥ 99% em produção.
- **RNF-003 (Latência):** O tempo percorrido entre a recepção do pacote pelo ChirpStack e a visualização no WebSocket do frontend deve ser ≤ 2 segundos.
- **RNF-004 (Segurança em Trânsito):** Toda a comunicação externa e entre microserviços em diferentes redes (HTTPS/gRPC) deve obrigatoriamente utilizar TLS.
- **RNF-005 (Autenticação):** Acesso a APIs deve utilizar JWT ou OAuth2.
- **RNF-006 (Observabilidade):** O sistema deve manter registro (Logs) de acesso, consumo de CPU/Memória dos contêineres, métricas do MQTT e telemetria básica.

---

## 7. Arquitetura de Alto Nível

A arquitetura move toda a inteligência para a AWS (Cloud), reduzindo o hardware nas instalações do cliente a componentes passivos de rede de sensores.

!Arquitetura LINX - LoRaWAN Intelligence Nexus.jpg

---

## 8. Principais Tecnologias

| Camada | Tecnologia | Justificativa |
| --- | --- | --- |
| **IoT / Rádio** | LoRaWAN (915 MHz) | Comunicação de baixo consumo de bateria e longo alcance. |
| **Network Server** | ChirpStack v4 | Gerenciamento open-source líder da infraestrutura LoRaWAN. |
| **Mensageria** | MQTT | Protocolo leve e assíncrono padrão para telemetria IoT. |
| **Backend API** | Python + FastAPI | Alta performance (assíncrono), documentação Swagger nativa. |
| **RPC** | gRPC | Comunicação rápida, tipada e eficiente entre microserviços da nuvem. |
| **Persistência Central** | PostgreSQL | Confiabilidade relacional para dados de organizações e usuários. |
| **Persistência das Apps** | TimescaleDB + Postgre | Otimização massiva para séries temporais e dados de sensores. |
| **Infraestrutura** | Docker | Isolamento perfeito para provisionar as Aplicações dinamicamente. |

---

## 9. Fluxos de Comunicação Estratégicos

### 9.1. Fluxo de Telemetria (Uplink)

1. **Sensor** transmite pacote RF.
2. **Gateway** recebe e encaminha via rede IP para o **ChirpStack** na AWS.
3. **ChirpStack** decifra o pacote e publica o evento no **MQTT Broker**.
4. **SaaS Backend** intercepta a mensagem, verifica a qual Aplicação o *DevEUI* pertence e realiza o roteamento.
5. Os dados são persistidos no **TimescaleDB** isolado da Aplicação e enviados via **WebSocket** para o Frontend.

### 9.2. Fluxo de Acionamento (Downlink / Comando)

1. Motor de Regras no **Docker da Aplicação** constata anomalia (ou Operador clica em "Ligar").
2. **Client Agent API** envia requisição HTTPS/REST ao **SaaS Backend**.
3. **SaaS Backend** valida a permissão e aciona o **ChirpStack** via chamada **gRPC** (Middleware).
4. **ChirpStack** enfileira a mensagem. Na próxima janela de transmissão (RX), envia o pacote de rádio ao **Gateway**, que aciona o equipamento final.

---

## 10. Segurança Arquitetural

A arquitetura adota o princípio de privilégio mínimo (*least privilege*) e criptografia em todas as etapas:

- **Dispositivos Físicos:** Validação nativa do protocolo LoRaWAN (AES-128, NwkSKey, AppSKey) contra *replay attacks*.
- **SaaS API (Borda da Nuvem):** HTTPS/TLS para tráfego web. Controle de usuários e senhas protegidas com `bcrypt` e JWT/OAuth2.
- **Isolamento de Contêineres:** Um *Docker Cliente* de uma Aplicação não tem rota de rede direta para o banco de dados de outra Aplicação, garantindo segurança a nível de infraestrutura.

---

## 11. Métricas de Sucesso — KPIs

| Categoria | KPI | Meta Inicial |
| --- | --- | --- |
| **Infraestrutura** | Uptime do SaaS Core | ≥ 99% |
| **Performance** | Latência de entrega (Sensor → Dashboard) | ≤ 2 segundos |
| **Confiabilidade** | Taxa de entrega de pacotes MQTT recebidos | ≥ 99.5% |
| **Produto/UX** | Tempo médio de provisionamento de nova Aplicação | ≤ 60 segundos (Automação) |
| **Produto/UX** | Taxa de sucesso no cadastro de sensores por QR Code | > 95% sem suporte manual |

---

## 12. Critérios de Aceitação do MVP

O MVP (Minimum Viable Product) acadêmico/inicial será considerado concluído quando provar o fluxo completo em nuvem:

1. **Multilocação:** Criação de pelo menos duas "Aplicações" via SaaS Backend, gerando dois contêineres Docker independentes e isolados.
2. **Onboarding Ágil:** Cadastro de dispositivo funcional via extração de dados do QR Code.
3. **Uplink:** Visualização da telemetria real do sensor fluindo do Gateway → ChirpStack → MQTT → SaaS → Docker da Aplicação → WebSocket (Frontend).
4. **Downlink/Regras:** Criação de uma regra simples de acionamento reverso operando a partir da Aplicação até o dispositivo físico via gRPC.
5. **Segurança:** Comprovação de uso de HTTPS/TLS, JWT nas rotas e persistência de dados segregada por aplicação.

---

## 13. Roadmap de Produto

- **Fase 1 — Core Cloud:** Deploy na AWS do SaaS Backend, ChirpStack, MQTT e PostgreSQL Central.
- **Fase 2 — Orquestração de Aplicações:** Desenvolvimento da rotina automatizada de criação do *Docker Cliente* (Client Agent + TimescaleDB) para cada nova Aplicação.
- **Fase 3 — Plug and Play e Dados:** Leitura de QR Code, fluxo ponta-a-ponta de telemetria e integração WebSocket.
- **Fase 4 — Lógica e Downlink:** Motor de confirmação de regras e roteamento de comandos via gRPC.
- **Fase 5 — Observabilidade e Alertas:** Serviço de notificações (Telegram/Email), monitoramento de saúde dos contêineres e detecção de quedas de Gateways.

---

## 14. Riscos do Produto

| Risco | Probabilidade | Impacto | Mitigação |
| --- | --- | --- | --- |
| **Dependência Exclusiva de Internet** | Alta | Muito Alto | Como o processamento foi para a nuvem, falhas de link local impedem acionamentos. Exigir do cliente nobreaks e redundância 4G nos Gateways LoRaWAN. |
| **Gargalo no Orquestrador Docker** | Média | Alto | A criação de muitas aplicações simultâneas pode sobrecarregar a AWS. Utilizar arquiteturas auto-escaláveis (Amazon ECS/EKS ou automação Terraform). |
| **Inconsistência de Dados (Sistemas Distribuídos)** | Média | Alto | Filas MQTT e regras gRPC podem gerar falhas silenciosas. Implementar identificação única e políticas de Retry/Dead Letter Queues. |
| **Crescimento Exponencial de Custos AWS** | Alta | Médio | Cada aplicação consome um Docker. Implementar política de *sleep/hibernate* para instâncias inativas ou adotar rateio rígido de custos no *billing* do SaaS. |