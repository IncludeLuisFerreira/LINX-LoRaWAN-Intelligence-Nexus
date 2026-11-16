# CI/CD do cluster K3s na AWS (issue #278)

O provisionamento do cluster K3s da sandbox era feito pelo Terraform em
`infra/terraform`, com state remoto no backend S3 (`linx-k3s-tfstate`) e lock
nativo do bucket (`use_lockfile`, sem DynamoDB); o bucket é criado uma única vez
pelo bootstrap manual.

> **Estado atual:** o workflow de CI `.github/workflows/terraform.yml` foi
> removido na [issue #287](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/287).
> Não há mais `apply`/`destroy` automatizado nem deploy de manifests pelo
> GitHub Actions. O `apply` e o `destroy` devem ser executados localmente, com
> credenciais próprias, e o deploy dos manifests passa a ser manual: como a
> porta 6443 do K3s é restrita à VPC, o `kubectl` roda no master via SSH, com o
> namespace `linx`, o Secret `linx-secrets` e `kubectl apply -k infra/kubernetes`.

O passo a passo completo — bootstrap, apply/destroy, deploy e diagnóstico — está no runbook
[`infra/terraform/README.md`](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/blob/develop/infra/terraform/README.md); o contexto e os
critérios de aceite estão na
[issue #278](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/278).
