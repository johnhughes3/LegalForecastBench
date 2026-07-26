variable "aws_region" {
  description = "AWS region containing the pre-existing provider spend authority table."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix for the protected paid-labeling IAM role."
  type        = string
  default     = "legalforecastbench-official-labeling"

  validation {
    condition     = can(regex("^[a-z0-9+=,.@_-]{3,48}$", var.name_prefix))
    error_message = "name_prefix must be a valid, bounded IAM role-name prefix."
  }
}

variable "github_oidc_provider_arn" {
  description = "ARN of the existing token.actions.githubusercontent.com OIDC provider."
  type        = string

  validation {
    condition = can(regex(
      "^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:oidc-provider/token[.]actions[.]githubusercontent[.]com$",
      var.github_oidc_provider_arn,
    ))
    error_message = "github_oidc_provider_arn must name the GitHub Actions OIDC provider."
  }
}

variable "github_subject_prefix" {
  description = "Exact GitHub OIDC repository subject prefix."
  type        = string
  default     = "repo:johnhughes3/LegalForecastBench"

  validation {
    condition = (
      var.github_subject_prefix == "repo:johnhughes3/LegalForecastBench"
    )
    error_message = "github_subject_prefix must remain the exact reviewed LegalForecastBench repository."
  }
}

variable "labeling_environment_names" {
  description = "Exact protected environments admitted by the labeling role trust policy."
  type        = set(string)
  default = [
    "legalforecastbench-official-labeling-authority-smoke",
    "legalforecastbench-official-labeling-anthropic-unitize",
    "legalforecastbench-official-labeling-google-label",
    "legalforecastbench-official-labeling-google-review",
    "legalforecastbench-official-labeling-openai-label",
  ]

  validation {
    condition = var.labeling_environment_names == toset([
      "legalforecastbench-official-labeling-authority-smoke",
      "legalforecastbench-official-labeling-anthropic-unitize",
      "legalforecastbench-official-labeling-google-label",
      "legalforecastbench-official-labeling-google-review",
      "legalforecastbench-official-labeling-openai-label",
    ])
    error_message = "labeling_environment_names must remain the exact reviewed stage/provider allowlist."
  }
}

variable "provider_authority_table_arn" {
  description = "Exact ARN of the pre-existing shared provider spend authority table."
  type        = string

  validation {
    condition = can(regex(
      "^arn:aws[a-zA-Z-]*:dynamodb:[a-z0-9-]+:[0-9]{12}:table/[A-Za-z0-9_.-]+$",
      var.provider_authority_table_arn,
    ))
    error_message = "provider_authority_table_arn must be one exact DynamoDB table ARN."
  }
}

variable "provider_authority_resource_identity_sha256" {
  description = "SHA-256 of provider_authority_table_arn frozen into provider-cycle-caps."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.provider_authority_resource_identity_sha256))
    error_message = "provider_authority_resource_identity_sha256 must be a lowercase SHA-256 digest."
  }
}

variable "tags" {
  description = "Additional non-sensitive AWS resource tags."
  type        = map(string)
  default     = {}
}
