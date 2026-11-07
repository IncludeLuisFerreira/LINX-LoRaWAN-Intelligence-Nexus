###############################################################################
# Terraform — Cluster K3s leve na AWS Sandbox (Learner Lab)
# Região: us-east-1 | Backend local (sem S3 remoto)
###############################################################################

terraform {
  required_version = ">= 1.3.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
  # Backend local por padrão — nada de S3 remoto.
}

provider "aws" {
  region = "us-east-1"
  # Credenciais locais a partir das credenciais temporárias do Learner Lab
  # (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN no ambiente).
}

###############################################################################
# Variáveis
###############################################################################

variable "key_name" {
  description = "Nome do EC2 Key Pair já existente no Sandbox (para SSH)."
  type        = string
}

variable "node_count" {
  description = "Número de workers."
  type        = number
  default     = 2
}

###############################################################################
# Token do cluster — gerado automaticamente
###############################################################################

resource "random_password" "k3s_token" {
  length  = 64
  special = false
}

###############################################################################
# Data — AMI Ubuntu 22.04 LTS (Canonical)
###############################################################################

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

###############################################################################
# Network — VPC simplificada
###############################################################################

resource "aws_vpc" "k3s" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "k3s-vpc"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.k3s.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "k3s-public-subnet"
  }
}

resource "aws_internet_gateway" "k3s" {
  vpc_id = aws_vpc.k3s.id

  tags = {
    Name = "k3s-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.k3s.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.k3s.id
  }

  tags = {
    Name = "k3s-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

###############################################################################
# Security Group
###############################################################################

resource "aws_security_group" "k3s" {
  name        = "k3s-cluster-sg"
  description = "SG para o cluster K3s"
  vpc_id      = aws_vpc.k3s.id

  # Tráfego interno entre nós (auto-referência, todas as portas).
  ingress {
    description = "All traffic internal cluster nodes"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  # SSH.
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # API do K3s (agent -> server) dentro da VPC.
  # Restrito ao CIDR da VPC: o acesso externo e via SSH, nao via 6443.
  ingress {
    description = "K3s API inside VPC"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  # NodePort para testes.
  ingress {
    description = "NodePort range"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Egress total.
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "k3s-cluster-sg"
  }
}

###############################################################################
# EC2 — Master (K3s server)
###############################################################################

resource "aws_instance" "master" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t3.medium"
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.k3s.id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  user_data = <<-EOT
#!/bin/bash
set -eux

export K3S_TOKEN="${random_password.k3s_token.result}"

# Instala o K3s server.
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server" sh -s -

# Expõe o kubeconfig para uso local.
mkdir -p /home/ubuntu/.kube
for i in $(seq 1 60); do
  if [ -f /etc/rancher/k3s/k3s.yaml ] && systemctl is-active --quiet k3s; then
    break
  fi
  sleep 2
done

if [ ! -f /etc/rancher/k3s/k3s.yaml ]; then
  echo "K3s kubeconfig não encontrado após 120s" >&2
  exit 1
fi

cp /etc/rancher/k3s/k3s.yaml /home/ubuntu/.kube/config
chown ubuntu:ubuntu /home/ubuntu/.kube/config
EOT

  tags = {
    Name = "k3s-master"
    Role = "server"
  }
}

###############################################################################
# EC2 — Workers (K3s agents)
###############################################################################

resource "aws_instance" "worker" {
  count                       = var.node_count
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t3.small"
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.k3s.id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  user_data = <<-EOT
#!/bin/bash
set -eux

MASTER_URL="https://${aws_instance.master.private_ip}:6443"
export K3S_URL="$MASTER_URL"
export K3S_TOKEN="${random_password.k3s_token.result}"

# Espera a API do K3s server ficar saudável antes de registrar o agent.
for i in $(seq 1 90); do
  if curl -ksf "$MASTER_URL/healthz" >/dev/null; then
    break
  fi
  sleep 2
done

if ! curl -ksf "$MASTER_URL/healthz" >/dev/null; then
  echo "K3s master não respondeu em $MASTER_URL após 180s" >&2
  exit 1
fi

# Instala o K3s agent apontando para o master.
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="agent" sh -s -
EOT

  depends_on = [aws_instance.master]

  tags = {
    Name = "k3s-worker-${count.index}"
    Role = "agent"
  }
}

###############################################################################
# Outputs
###############################################################################

output "master_public_ip" {
  description = "IP público da instância Master."
  value       = aws_instance.master.public_ip
}

output "ssh_command" {
  description = "Comando SSH pronto para o Master."
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_instance.master.public_ip}"
}

output "worker_private_ips" {
  description = "IPs privados dos Workers."
  value       = aws_instance.worker[*].private_ip
}

output "k3s_token" {
  description = "Token do cluster K3s gerado automaticamente (sensível)."
  value       = random_password.k3s_token.result
  sensitive   = true
}
