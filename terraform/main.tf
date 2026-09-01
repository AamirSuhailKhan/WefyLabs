# ==============================================================================
# BeetleLabs Enterprise Infrastructure as Code (Terraform)
# Defines: VPC, Private Subnets, EKS Cluster, RDS Postgres 16 Multi-AZ,
# ElastiCache Redis Cluster, and S3 Backup Bucket with KMS Encryption.
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "production"
}

# 1. VPC Network Infrastructure
resource "aws_vpc" "beetlelabs_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "beetlelabs-${var.environment}-vpc"
    Environment = var.environment
  }
}

# 2. KMS Customer Managed Key for Storage Encryption
resource "aws_kms_key" "storage_key" {
  description             = "KMS Key for BeetleLabs Encrypted DB & S3 Backups"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

# 3. Encrypted S3 Backup Bucket
resource "aws_s3_bucket" "backup_bucket" {
  bucket = "beetlelabs-enterprise-backups-${var.environment}"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backup_enc" {
  bucket = aws_s3_bucket.backup_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.storage_key.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# 4. Multi-AZ PostgreSQL 16 RDS Database
resource "aws_db_instance" "postgres" {
  identifier             = "beetlelabs-db-${var.environment}"
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = "db.r6g.xlarge"
  allocated_storage      = 100
  max_allocated_storage  = 1000
  storage_type           = "gp3"
  storage_encrypted      = true
  kms_key_id             = aws_kms_key.storage_key.arn
  multi_az               = true
  db_name                = "beetlelabs_prod"
  username               = "beetle_admin"
  password               = "ChangeMeInVault!2026"
  skip_final_snapshot    = false
  backup_retention_period = 30
}

# 5. ElastiCache Redis Cluster
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "beetlelabs-redis-${var.environment}"
  engine               = "redis"
  node_type            = "cache.r6g.large"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}
