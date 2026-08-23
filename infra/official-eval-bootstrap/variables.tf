variable "aws_region" {
  description = "AWS region for the state bucket, KMS key, and reviewed Terraform roots."
  type        = string

  validation {
    condition     = can(regex("^[a-z]{2}(-gov)?-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be an explicit AWS region name."
  }
}

variable "state_bucket_name" {
  description = "Globally unique private S3 bucket that will own LFB Terraform state."
  type        = string

  validation {
    condition = (
      can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.state_bucket_name)) &&
      !strcontains(var.state_bucket_name, "..") &&
      length(regexall("^[0-9]{1,3}([.][0-9]{1,3}){3}$", var.state_bucket_name)) == 0
    )
    error_message = "state_bucket_name must satisfy the S3 general-purpose bucket naming rules."
  }
}

variable "state_key_prefix" {
  description = "Prefix containing only the three reviewed workflow-managed Terraform state keys."
  type        = string

  validation {
    condition = (
      can(regex("^[a-z0-9][a-z0-9/_-]{0,127}$", var.state_key_prefix)) &&
      !startswith(var.state_key_prefix, "/") &&
      !endswith(var.state_key_prefix, "/") &&
      !strcontains(var.state_key_prefix, "//") &&
      !strcontains(var.state_key_prefix, "..")
    )
    error_message = "state_key_prefix must be a bounded relative S3 key prefix."
  }
}

variable "bootstrap_state_key" {
  description = "Human-controlled state key for this bootstrap root; never granted to the routine operator role."
  type        = string
  default     = "bootstrap/terraform.tfstate"

  validation {
    condition     = var.bootstrap_state_key == "bootstrap/terraform.tfstate"
    error_message = "bootstrap_state_key must remain outside the routine workflow prefix."
  }
}

variable "kms_alias_name" {
  description = "Stable alias for the customer-managed Terraform state key."
  type        = string
  default     = "alias/legalforecastbench-official-terraform-state"

  validation {
    condition = (
      var.kms_alias_name == "alias/legalforecastbench-official-terraform-state"
    )
    error_message = "kms_alias_name must remain the reviewed LFB state-key alias."
  }
}

variable "operator_role_name" {
  description = "Exact short-lived GitHub OIDC role used by the reviewed infrastructure workflow."
  type        = string
  default     = "legalforecastbench-official-provider-authority-infra"

  validation {
    condition = (
      var.operator_role_name == "legalforecastbench-official-provider-authority-infra"
    )
    error_message = "operator_role_name must remain the reviewed infrastructure operator role."
  }
}

variable "github_repository" {
  description = "Exact externally supplied GitHub owner/repository admitted by the operator-role trust policy."
  type        = string

  validation {
    condition = (
      can(regex("^[A-Za-z0-9][A-Za-z0-9_.-]{0,38}/[A-Za-z0-9_.-]{1,100}$", var.github_repository)) &&
      alltrue([for component in split("/", var.github_repository) : !contains([".", ".."], component)])
    )
    error_message = "github_repository must be an exact bounded GitHub owner/repository name."
  }
}

variable "github_environment" {
  description = "Exact protected GitHub environment admitted by the operator-role trust policy."
  type        = string
  default     = "legalforecastbench-official-provider-authority-infra"

  validation {
    condition = (
      var.github_environment == "legalforecastbench-official-provider-authority-infra"
    )
    error_message = "github_environment must remain the reviewed infrastructure environment."
  }
}

variable "provider_authority_table_name" {
  description = "Exact DynamoDB table managed by the provider-authority Terraform root."
  type        = string
  default     = "legalforecastbench-official-eval-provider-authority"

  validation {
    condition = (
      var.provider_authority_table_name == "legalforecastbench-official-eval-provider-authority"
    )
    error_message = "provider_authority_table_name must remain the reviewed table name."
  }
}

variable "outside_authority_table_name" {
  description = "Exact disposable DynamoDB canary managed by the provider-authority Terraform root for the provider-free permission smoke."
  type        = string
  default     = "legalforecastbench-official-labeling-authority-smoke-canary"

  validation {
    condition = (
      var.outside_authority_table_name == "legalforecastbench-official-labeling-authority-smoke-canary"
    )
    error_message = "outside_authority_table_name must remain the reviewed disposable authority-smoke canary name."
  }
}

variable "official_labeling_role_name" {
  description = "Exact IAM role managed by the official-labeling Terraform root."
  type        = string
  default     = "legalforecastbench-official-labeling-authority"

  validation {
    condition = (
      var.official_labeling_role_name == "legalforecastbench-official-labeling-authority"
    )
    error_message = "official_labeling_role_name must remain the reviewed labeling role."
  }
}

variable "official_eval_cell_role_name" {
  description = "Exact official-eval provider-cell IAM role whose session maximum the reviewed apply may update."
  type        = string
  default     = "legalforecastbench-official-eval"

  validation {
    condition = (
      var.official_eval_cell_role_name == "legalforecastbench-official-eval"
    )
    error_message = "official_eval_cell_role_name must remain the reviewed provider-cell role."
  }
}

variable "tags" {
  description = "Additional non-sensitive AWS resource tags."
  type        = map(string)
  default     = {}
}
