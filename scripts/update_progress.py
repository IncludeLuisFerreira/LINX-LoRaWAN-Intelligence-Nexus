#!/usr/bin/env python3
"""Regenera o PROGRESS.md a partir do estado atual das issues do GitHub.

Uso:
    make progress        # ou: python3 scripts/update_progress.py

Marca [x] para issues fechadas e [ ] para abertas, agrupadas por sprint.
Requer a GitHub CLI (`gh`) autenticada.
"""
import json
import subprocess

REPO = "IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus"

THEMES = {
    "Sprint 1": "Fundação e Contratos",
    "Sprint 2": "Dois Serviços na AWS com gRPC",
    "Sprint 3": "ChirpStack, Uplink Ponta-a-Ponta e WebSocket",
    "Sprint 4": "Multi-Tenant Real: Provisionamento Automático",
    "Sprint 5": "Autenticação, RBAC e TLS",
    "Sprint 6": "Motor de Regras, Downlink e Alertas",
    "Sprint 7": "Resiliência: Retry, Circuit Breaker e DLQ",
    "Sprint 8": "Observabilidade, Hardening e Demo Final",
}


def main():
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", REPO, "--state", "all",
         "--json", "number,title,state,milestone,url", "--limit", "1000"],
        capture_output=True, text=True, check=True,
    )
    issues = json.loads(out.stdout)

    by_sprint = {}
    order = []
    for i in issues:
        ms = i.get("milestone") or {}
        name = ms.get("title")
        if not name or not name.startswith("Sprint"):
            continue
        if name not in by_sprint:
            by_sprint[name] = []
            order.append(name)
        by_sprint[name].append(i)

    order.sort(key=lambda t: int(t.split()[1]))
    for name in by_sprint:
        by_sprint[name].sort(key=lambda i: i["number"])

    lines = [
        "# Progresso — LINX", "",
        "> Acompanhamento do desenvolvimento. Checkbox marcado = issue fechada.", "",
    ]
    total = 0
    done = 0
    for name in order:
        theme = THEMES.get(name, "")
        heading = f"{name} — {theme}" if theme else name
        lines.append(f"## {heading}")
        lines.append("")
        for i in by_sprint[name]:
            mark = "x" if i["state"] == "closed" else " "
            lines.append(f"- [{mark}] [#{i['number']} {i['title']}]({i['url']})")
            total += 1
            if i["state"] == "closed":
                done += 1
        lines.append("")
    lines.append(f"**Total de issues:** {total} ({done} concluídas)")

    with open("PROGRESS.md", "w") as f:
        f.write("\n".join(lines))

    print(f"PROGRESS.md atualizado: {done}/{total} issues concluídas.")


if __name__ == "__main__":
    main()
