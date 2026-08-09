terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # The first apply deliberately uses `terraform init -backend=false` and
  # protected local state. This partial backend is activated only when that
  # verified state is migrated into the bucket created by this root.
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        ManagedBy = "terraform"
        Project   = "LegalForecastBench"
        Purpose   = "official-eval-bootstrap"
      },
      var.tags,
    )
  }
}

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}
