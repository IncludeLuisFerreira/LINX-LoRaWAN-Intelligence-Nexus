# AGENTS.md — Orquestração de Agentes de IA

Bem-vindo, agente. Você está trabalhando com **outros agentes de IA em paralelo neste repositório** (LINX). Stack principal: Python/FastAPI (`linx_core/`), React 19 + TypeScript + Tailwind (`client/frontend/`, veja `package.json`), gRPC (`proto/`), Docker. Entry points de validação: `pytest` (config em `pyproject.toml`), `npm run test` e `npm run lint` (em `client/frontend/`, veja `package.json`). O `Makefile` contém apenas alvos de infraestrutura Docker (up/build/down/logs) — não tem test/lint.

> **Precedência de documentos aninhados:** um `AGENTS.md` em subdiretório (ex.: `website/AGENTS.md`) complementa e refina estas diretrizes; em conflito, vale a regra mais estrita e as regras gerais deste arquivo na raiz prevalecem para comandos destrutivos e escopo de arquivos alheios.

A seguir estão as regras obrigatórias. Elas existem para impedir que um agente incorpore, sobrescreva ou apague o trabalho de outro agente.

## 1. Regra principal — escopo estrito da task

Você deve **apenas modificar, commitar e pushear arquivos que têm relação com a sua task/issue**. Nada além disso.

- Leia a issue designada antes de qualquer ação. Seu escopo é o escopo da issue — nem mais, nem menos. Toda task deve ter uma issue correspondente; se não houver, crie a issue primeiro.
- Não "aprove a passagem" para corrigir bugs, refatorar ou atualizar documentação fora de escopo. Se detectar um problema fora do seu escopo, **reporte** no relatório final (ou na issue correspondente), mas não mexa.

## 2. Antes de agir — mapeamento do território

Sempre que iniciar uma task, e novamente antes de qualquer commit, faça um levantamento do estado atual:

1. `git status` e `git diff --stat` — identifique arquivos rastreados com modificações que **não são seus**.
2. Liste arquivos não rastreados (`untracked`). Eles geralmente pertencem ao agente que os criou. **Nunca** remova, sobrescreva ou incorpore aos seus commits o arquivo de outro agente sem autorização explícita do humano.
3. Verifique a branch atual. Se ela não for sua, não commite nela e **não faça checkout para outra branch no working tree atual** — isso muda o HEAD de quem o estiver usando. Use um `git worktree` em diretório separado para isolar seu trabalho.
4. Consulte `docs/superpowers/plans/` e arquivos de instruções/logs de outros agentes (ex.: avisos do tipo `DO-NOT-COMMIT-THIS.txt`) para entender o trabalho em andamento e respeitar seus contratos.

**Se houver qualquer dúvida sobre a quem pertence um arquivo ou branch: pergunte. Não conclua sozinho.**

## 3. Comandos destrutivos — proibidos

O working tree pode conter trabalho em andamento de **outros agentes**. Isso significa que comandos que apagam ou reescrevem estado local são proibidos **sem verificação explícita de que afetam apenas arquivos seus**, e em geral proibidos por padrão:

- `git clean` de qualquer variante (`-f`, `-fd`, `-fdx`) — apaga untracked files, possivelmente de outro agente.
- `git reset --hard` — descarta alterações rastreadas de todo o diretório.
- `git restore .` / `git checkout .` / `git checkout <arquivo de outro>` sem argumentos direcionados — descartam alterações em massa.
- `git stash` sobre o working tree compartilhado — pode capturar trabalho alheio no seu stash e depois sumir com ele.
- `git pull`/`git rebase`/`git push --force`/`--force-with-lease` em branch que **não** é sua (reescreve ou sobrescreve o histórico de outro agente).

Regras:

1. Nunca executar esses comandos por padrão. Se realmente precisar, **interrompa e peça orientação à pessoa humana**, listando exatamente o que será afetado (`git status` + `git diff` antes).
2. Comandos direcionados a arquivos **seus, e unicamente seus** (ex.: `git restore --staged src/minha-pasta/`) são permitidos após verificar a lista de caminhos.
3. Descarte de trabalho é uma ação irreversível: se não tiver certeza absoluta da propriedade do arquivo, não execute.

## 4. Branches e colaboração

- Uma branch por issue, nome descritivo (ex.: `feat/54-provisioning-status`), sempre a partir de `develop` **atualizada**. Para garantir o estado atualizado: `git fetch origin` e confirme com `git merge-base HEAD origin/develop` == `git rev-parse origin/develop` (ou `git log HEAD..origin/develop --oneline` vazio) que não há commits novos em `origin/develop`.
- Não commite na branch de outra task. Se a sua task começou por engano em uma branch de outra issue, **não commite nada** — interrompa, explique a situação e peça orientação.
- **Rebase/amend só antes do primeiro push** da sua branch — depois do primeiro push, o histórico é público e não deve ser reescrito, exceto em um caso: para resolver feedback de review em uma **PR aberta sua**, você pode rebase/amend e atualizar com `git push --force-with-lease`. Essa exceção vale somente na **sua** branch de PR aberta; nunca após a branch ser mergeada em `develop` e nunca em branch compartilhada (usada por outro agente) — nesses casos, prefira merge de `origin/develop` na sua branch ou um novo commit que resolva o problema.
- Ao atualizar `develop` ou fazer rebase, confirme que nenhum arquivo de outro agente será afetado.

## 5. Commits

- Use Conventional Commits, referenciando a issue (ex.: `feat(frontend): ... (#54)`). Commits sem referência à issue não atendem à convenção.
- **`git add` explícito, arquivo por arquivo.** Nunca use `git add .`, `git add -A` ou `git commit -a` — eles agregam trabalho alheio.
- Antes de cada commit: revise `git status --short` e o diff completo (`git diff --cached`) e confirme que **todos** os arquivos stageados são seus. Qualquer arquivo estranho na área de staging → remova do stage (`git restore --staged <arquivo>`) e investigue.
- Nunca commite segredos, chaves, `.env` real (apenas `.env.example`) ou artefatos gerados que o `.gitignore` cobre.
- Teste o código antes de commitar: rode os testes, lint e typecheck pertinentes à sua task e registre os resultados reais. Não declare sucesso sem executar.

## 6. Push e Pull Request

- Push apenas da **sua** branch, para **sua** issue.
- Uma PR por issue, com a issue vinculada no título ou corpo (ex.: `docs(governance): ... (#227)`), e com a issue fechada quando apropriado.
- PRs devem descrever: o que foi feito, por que, lista de arquivos alterados, como testar (passos de teste manual incluídos), o que o CI **não** cobre automaticamente (confira `paths:` em `.github/workflows/*.yml` antes de afirmar que um workflow roda) e pendências identificadas.
- PRs não devem conter arquivos de outras issues, mesmo que "preparados" por você ou visíveis no diretório de trabalho.
- **Sem merge automático.** Merge só com autorização explícita após code review.

## 7. Conduta geral

- Não suponha que arquivos, funções ou contratos existem — verifique antes de usar.
- Preserve as convenções do projeto (idioma dos commits e PR: português, padrão do repositório).
- Não oculte falhas. Se testes falharem, documente a falha em vez de ajustar o teste à força.
- Se surgir dependência não prevista, conflito com outro agente ou mudança de escopo: **interrompa e peça orientação à pessoa humana.**

## 8. Encerramento da task

Ao final, informe: arquivos criados/alterados (somente os seus), comandos de validação executados e resultados, PR criada (link, número, branch origem/destino) e pendências. Em seguida, aguarde revisão — não inicie outra task sem ser designado.
