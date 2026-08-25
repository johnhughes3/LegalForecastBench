variable "aws_region" {
  description = "AWS region containing the existing official packet and result buckets."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Stable prefix for the two official-evaluation IAM roles."
  type        = string
  default     = "legalforecastbench-official-eval"

  validation {
    condition     = can(regex("^[a-z0-9+=,.@_-]{3,48}$", var.name_prefix))
    error_message = "name_prefix must be a bounded IAM role-name prefix."
  }
}

variable "github_oidc_provider_arn" {
  description = "ARN of the existing account-level GitHub Actions OIDC provider."
  type        = string

  validation {
    condition = can(regex(
      "^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:oidc-provider/token[.]actions[.]githubusercontent[.]com$",
      var.github_oidc_provider_arn,
    ))
    error_message = "github_oidc_provider_arn must name the GitHub Actions OIDC provider."
  }
}

variable "provider_authority_table_arn" {
  description = "Exact DynamoDB table ARN for official-evaluation provider attempt authority."
  type        = string

  validation {
    condition = (
      can(regex(
        "^arn:aws[a-zA-Z-]*:dynamodb:[a-z0-9-]+:[0-9]{12}:table/[A-Za-z0-9_.-]{3,255}$",
        var.provider_authority_table_arn,
      )) &&
      !strcontains(var.provider_authority_table_arn, "*") &&
      !strcontains(var.provider_authority_table_arn, "?")
    )
    error_message = "provider_authority_table_arn must be one exact DynamoDB table ARN without wildcards."
  }
}

variable "provider_authority_resource_identity_sha256" {
  description = "Frozen lowercase SHA-256 commitment of provider_authority_table_arn."
  type        = string

  validation {
    condition = can(regex(
      "^[0-9a-f]{64}$",
      var.provider_authority_resource_identity_sha256,
    ))
    error_message = "provider_authority_resource_identity_sha256 must be 64 lowercase hexadecimal characters."
  }
}

variable "packet_bucket_name" {
  description = "Existing private S3 bucket containing model-visible packets."
  type        = string

  validation {
    condition = (
      can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.packet_bucket_name)) &&
      !strcontains(var.packet_bucket_name, "..") &&
      length(regexall("^[0-9]{1,3}([.][0-9]{1,3}){3}$", var.packet_bucket_name)) == 0 &&
      !startswith(var.packet_bucket_name, "xn--") &&
      !startswith(var.packet_bucket_name, "sthree-") &&
      !startswith(var.packet_bucket_name, "amzn-s3-demo-") &&
      !endswith(var.packet_bucket_name, "-s3alias") &&
      !endswith(var.packet_bucket_name, "--ol-s3") &&
      !endswith(var.packet_bucket_name, ".mrap") &&
      !endswith(var.packet_bucket_name, "--x-s3") &&
      !endswith(var.packet_bucket_name, "--table-s3") &&
      !endswith(var.packet_bucket_name, "-an")
    )
    error_message = "packet_bucket_name must satisfy the S3 global-namespace general purpose bucket naming rules."
  }
}

variable "results_bucket_name" {
  description = "Existing private S3 bucket containing official manifests, durable results, receipts, and reports."
  type        = string

  validation {
    condition = (
      can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.results_bucket_name)) &&
      !strcontains(var.results_bucket_name, "..") &&
      length(regexall("^[0-9]{1,3}([.][0-9]{1,3}){3}$", var.results_bucket_name)) == 0 &&
      !startswith(var.results_bucket_name, "xn--") &&
      !startswith(var.results_bucket_name, "sthree-") &&
      !startswith(var.results_bucket_name, "amzn-s3-demo-") &&
      !endswith(var.results_bucket_name, "-s3alias") &&
      !endswith(var.results_bucket_name, "--ol-s3") &&
      !endswith(var.results_bucket_name, ".mrap") &&
      !endswith(var.results_bucket_name, "--x-s3") &&
      !endswith(var.results_bucket_name, "--table-s3") &&
      !endswith(var.results_bucket_name, "-an")
    )
    error_message = "results_bucket_name must satisfy the S3 global-namespace general purpose bucket naming rules."
  }
}

variable "artifacts_kms_key_arn" {
  description = "Exact customer-managed KMS key ARN used by both existing artifact buckets. Aliases are not accepted."
  type        = string

  validation {
    condition = can(regex(
      "^arn:aws[a-zA-Z-]*:kms:[a-z0-9-]+:[0-9]{12}:key/[0-9a-fA-F-]{36}$",
      var.artifacts_kms_key_arn,
    ))
    error_message = "artifacts_kms_key_arn must be one exact KMS key ARN, not an alias."
  }
}

variable "enable_bedrock_runtime" {
  description = "Whether the cell role may use the separately reviewed direct-model and geographic inference-profile grants."
  type        = bool
  default     = false
}

variable "bedrock_direct_foundation_model_arns" {
  description = "Exact foundation-model ARNs that the cell may invoke directly, without an inference profile."
  type        = set(string)
  default     = []

  validation {
    condition = alltrue([
      for arn in var.bedrock_direct_foundation_model_arns :
      can(regex(
        "^arn:aws[a-zA-Z-]*:bedrock:[a-z0-9-]+::foundation-model/[A-Za-z0-9._:+-]+$",
        arn,
      )) && !strcontains(arn, "*") && !strcontains(arn, "?")
    ])
    error_message = "bedrock_direct_foundation_model_arns must contain only exact foundation-model ARNs without wildcards."
  }
}

variable "bedrock_geographic_inference_profiles" {
  description = "Exact non-global geographic inference profiles and the complete reviewed destination foundation-model ARN set for each profile."
  type = map(object({
    inference_profile_arn             = string
    destination_foundation_model_arns = set(string)
  }))
  default = {}

  validation {
    condition = alltrue([
      for profile in values(var.bedrock_geographic_inference_profiles) :
      !strcontains(
        lower(profile.inference_profile_arn),
        ":inference-profile/global.",
      )
    ])
    error_message = "Global Bedrock inference profiles are unsupported because they require a distinct three-part policy contract."
  }

  validation {
    condition = alltrue([
      for profile in values(var.bedrock_geographic_inference_profiles) :
      can(regex(
        "^arn:aws[a-zA-Z-]*:bedrock:[a-z0-9-]+:[0-9]{12}:inference-profile/(us|eu|apac)[.][A-Za-z0-9._:+-]+$",
        profile.inference_profile_arn,
      )) &&
      !strcontains(profile.inference_profile_arn, "*") &&
      !strcontains(profile.inference_profile_arn, "?") &&
      length(profile.destination_foundation_model_arns) > 0 &&
      alltrue([
        for destination_arn in profile.destination_foundation_model_arns :
        can(regex(
          "^arn:aws[a-zA-Z-]*:bedrock:[a-z0-9-]+::foundation-model/[A-Za-z0-9._:+-]+$",
          destination_arn,
        )) &&
        !strcontains(destination_arn, "*") &&
        !strcontains(destination_arn, "?") &&
        try(
          split(":", destination_arn)[1] == split(":", profile.inference_profile_arn)[1],
          false,
        )
      ])
    ])
    error_message = "Each geographic Bedrock inference profile must be an exact us.*, eu.*, or apac.* inference-profile ARN with a nonempty exact same-partition destination foundation-model ARN set."
  }

  validation {
    condition = length(distinct([
      for profile in values(var.bedrock_geographic_inference_profiles) :
      profile.inference_profile_arn
    ])) == length(var.bedrock_geographic_inference_profiles)
    error_message = "Each geographic Bedrock inference-profile ARN must appear in exactly one contract entry."
  }
}

variable "tags" {
  description = "Additional non-sensitive AWS resource tags."
  type        = map(string)
  default     = {}
}
