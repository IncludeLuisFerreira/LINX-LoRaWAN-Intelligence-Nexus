# Testes de ferramentas (`scripts/`)

Estes testes cobrem ferramentas de repositório (checkers, scripts de CI), não
código de aplicação. Eles usam **`unittest` da biblioteca padrão** de propósito:

- rodam sem instalar dependências (`python3 -m unittest ...`);
- não exigem Poetry, Docker, banco ou rede;
- podem rodar em qualquer máquina com Python 3.12+.

## Regra do repositório

| Tipo | Framework |
|---|---|
| Código de aplicação (`linx_core`, `services`, `middleware`, `client`) | `pytest` |
| Integração (`tests/integration`) | `pytest` |
| Ferramentas de repo (`scripts/`) | `unittest` (stdlib) |

O `pytest` coleta classes `unittest` sem alteração, então a mistura não quebra
nada. O contrário não vale: um teste escrito para `pytest` não roda com
`unittest` puro.

## Rodar

```bash
python3 -m unittest discover -s scripts/tests -t . -v
```
