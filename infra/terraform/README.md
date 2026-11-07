# Terraform — Cluster K3s (AWS Sandbox)

## Backend S3 — bootstrap (uma única vez)

O estado do Terraform fica em S3 com lock via DynamoDB. Antes do primeiro
`terraform init`, crie o bucket e a tabela de lock:

```bash
aws s3api create-bucket --bucket linx-k3s-tfstate --region us-east-1
aws s3api put-bucket-versioning --bucket linx-k3s-tfstate \
  --versioning-configuration Status=Enabled
aws dynamodb create-table \
  --table-name linx-k3s-tfstate-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

> Se `create-bucket` falhar com `BucketAlreadyExists`, troque
> `linx-k3s-tfstate` por um nome globalmente único no comando acima e no bloco
> `backend "s3"` de `main.tf`.

Depois:

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform plan
```
