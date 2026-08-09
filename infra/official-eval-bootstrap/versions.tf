terraform {
  required_version = ">= 1.11.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

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
