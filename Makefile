# O .PHONY avisa ao Make que essas palavras são nomes de comandos, e não nomes de arquivos físicos na pasta.
# Isso evita conflitos caso você crie um arquivo chamado "build" ou "logs" no futuro.
.PHONY: up down logs build stop-all progress

# COMANDO PARA PARAR TODOS OS CONTAINERS E SUBIR O NOVO
# O "up: stop-all" diz que o comando "stop-all" deve rodar ANTES do "up".
up: stop-all
	# -f infra/docker-compose.yml: aponta onde está o arquivo de configuração.
	# up -d: sobe os containers em segundo plano (detached mode), liberando o terminal.
	docker compose -f infra/docker-compose.yml up -d

# COMANDO PARA FORÇAR A RECONSTRUÇÃO DAS IMAGENS
build:
	# --build: força o Docker a ler o Dockerfile novamente e recriar a imagem do zero, 
	# ignorando o cache (muito útil quando você altera pacotes ou o código base).
	docker compose -f infra/docker-compose.yml up -d --build

# COMANDO PARA DERRUBAR OS CONTAINERS DO PROJETO
down:
	# down: para os containers deste projeto específico e remove as redes que foram criadas para ele.
	docker compose -f infra/docker-compose.yml down

# COMANDO PARA VER OS LOGS
logs:
	# logs -f: o "-f" (follow) mantém o terminal travado acompanhando os logs em tempo real, 
	# igual acontece quando não usamos o "-d" no comando up. Para sair, basta apertar Ctrl+C.
	docker compose -f infra/docker-compose.yml logs -f

# COMANDO PARA PARAR TUDO (IGNORA SE NÃO HOUVER CONTAINERS RODANDO)
stop-all:
	# docker ps -q: lista apenas os IDs numéricos dos containers que estão rodando agora.
	# | (pipe): pega o resultado do comando anterior e passa para o próximo.
	# xargs -r: pega os IDs e joga para o "docker stop". O "-r" diz para não fazer nada se a lista estiver vazia.
	docker ps -q | xargs -r docker stop

# COMANDO PARA ATUALIZAR O PROGRESS.MD COM O ESTADO ATUAL DAS ISSUES
# Rode após fechar/abrir issues para refletir o progresso (checkboxes [x]/[ ]).
progress:
	python3 scripts/update_progress.py