# CI/CD do cluster K3s na AWS (issue #278)

O provisionamento do cluster K3s da sandbox é feito pelo Terraform em
`infra/terraform`, com state remoto no backend S3 (`linx-k3s-tfstate`) e lock
nativo do bucket (`use_lockfile`, sem DynamoDB); o bucket é criado uma única vez
pelo bootstrap manual. O `apply` e o `destroy` rodam sob demanda pelo
`workflow_dispatch` de `.github/workflows/terraform.yml` (inputs `action` e
`key_name`), e o deploy dos manifests acontece no mesmo job: como o runner não
alcança a porta 6443 do K3s (restrita à VPC), o `kubectl` roda no master via SSH,
com o namespace `linx`, o Secret `linx-secrets` (a partir do secret
`LINX_SECRETS_ENV`) e `kubectl apply -k infra/kubernetes`. O passo a passo
completo — bootstrap, apply/destroy, deploy e diagnóstico — está no runbook
[`infra/terraform/README.md`](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/blob/develop/infra/terraform/README.md); o contexto e os
critérios de aceite estão na
[issue #278](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/278).
