locals {
  github_repository     = "johnhughes3/LegalForecastBench"
  github_ref            = "refs/heads/main"
  github_subject_prefix = "repo:${local.github_repository}"

  cell_environment_name             = "legalforecastbench-official-eval"
  prepare_inputs_environment_name   = "legalforecastbench-official-eval-prepare-inputs"
  fan_in_environment_name           = "legalforecastbench-official-eval-fan-in"
  manifest_staging_environment_name = "legalforecastbench-official-eval-manifest-staging"

  cell_subject = (
    "${local.github_subject_prefix}:environment:${local.cell_environment_name}"
  )
  prepare_inputs_subject = (
    "${local.github_subject_prefix}:environment:${local.prepare_inputs_environment_name}"
  )
  fan_in_subject = (
    "${local.github_subject_prefix}:environment:${local.fan_in_environment_name}"
  )
  manifest_staging_subject = (
    "${local.github_subject_prefix}:environment:${local.manifest_staging_environment_name}"
  )

  # The corpus repository opts into GitHub's immutable subject claim, so its
  # `sub` names the numeric owner and repository IDs rather than the mutable
  # owner/repository pair. Deriving the subject here rather than accepting it as
  # a free-form input keeps that contract visible to a reviewer and makes a
  # reverted claim customization fail closed: the default `sub` no longer
  # matches, and the role simply refuses the assume.
  corpus_github_repository_parts = split("/", var.corpus_github_repository)
  corpus_github_subject = join("", [
    "repo:${local.corpus_github_repository_parts[0]}@${var.corpus_github_repository_owner_id}",
    "/${local.corpus_github_repository_parts[1]}@${var.corpus_github_repository_id}",
    ":environment:${var.corpus_github_environment}",
  ])
  computed_provider_authority_resource_identity_sha256 = sha256(
    var.provider_authority_table_arn
  )
  artifact_bucket_partition = split(":", var.artifacts_kms_key_arn)[1]
  packet_bucket_arn         = "arn:${local.artifact_bucket_partition}:s3:::${var.packet_bucket_name}"
  results_bucket_arn        = "arn:${local.artifact_bucket_partition}:s3:::${var.results_bucket_name}"

  cell_trust_policy_json = templatefile(
    "${path.module}/policies/github-oidc-trust.json.tftpl",
    {
      github_oidc_provider_arn = var.github_oidc_provider_arn
      github_repository        = local.github_repository
      github_ref               = local.github_ref
      github_subject           = local.cell_subject
    },
  )
  fan_in_trust_policy_json = templatefile(
    "${path.module}/policies/github-oidc-trust.json.tftpl",
    {
      github_oidc_provider_arn = var.github_oidc_provider_arn
      github_repository        = local.github_repository
      github_ref               = local.github_ref
      github_subject           = local.fan_in_subject
    },
  )
  prepare_inputs_trust_policy_json = templatefile(
    "${path.module}/policies/github-oidc-trust.json.tftpl",
    {
      github_oidc_provider_arn = var.github_oidc_provider_arn
      github_repository        = local.github_repository
      github_ref               = local.github_ref
      github_subject           = local.prepare_inputs_subject
    },
  )
  # Manifest staging is the one lane both repositories drive: this repository
  # stages supplementary run inputs, and the corpus repository hands off the
  # release it issues. It therefore renders from its own two-statement template
  # rather than the shared single-subject one, so admitting the second
  # repository cannot change what the cell, prepare-inputs, or fan-in roles
  # trust. Each statement stays exactly pinned; neither uses a list or a
  # wildcard.
  manifest_staging_trust_policy_json = templatefile(
    "${path.module}/policies/manifest-staging-trust.json.tftpl",
    {
      github_oidc_provider_arn          = var.github_oidc_provider_arn
      github_repository                 = local.github_repository
      github_ref                        = local.github_ref
      github_subject                    = local.manifest_staging_subject
      corpus_github_repository          = var.corpus_github_repository
      corpus_github_repository_id       = var.corpus_github_repository_id
      corpus_github_repository_owner_id = var.corpus_github_repository_owner_id
      corpus_github_environment         = var.corpus_github_environment
      corpus_github_subject             = local.corpus_github_subject
    },
  )

  cell_storage_policy_json = templatefile(
    "${path.module}/policies/cell-storage-policy.json.tftpl",
    {
      artifacts_kms_key_arn = var.artifacts_kms_key_arn
      packet_bucket_arn     = local.packet_bucket_arn
      results_bucket_arn    = local.results_bucket_arn
    },
  )
  cell_provider_authority_policy_json = templatefile(
    "${path.module}/policies/cell-provider-authority-policy.json.tftpl",
    {
      provider_authority_table_arn = var.provider_authority_table_arn
    },
  )
  bedrock_invoke_model_statements = concat(
    length(var.bedrock_direct_foundation_model_arns) > 0 ? [
      {
        Sid      = "InvokeReviewedDirectFoundationModels"
        Effect   = "Allow"
        Action   = "bedrock:InvokeModel"
        Resource = sort(tolist(var.bedrock_direct_foundation_model_arns))
      },
    ] : [],
    flatten([
      for profile_key in sort(keys(var.bedrock_geographic_inference_profiles)) : [
        {
          Sid      = "GrantGeographicInferenceProfile${substr(sha256(profile_key), 0, 12)}Access"
          Effect   = "Allow"
          Action   = "bedrock:InvokeModel"
          Resource = [var.bedrock_geographic_inference_profiles[profile_key].inference_profile_arn]
        },
        {
          Sid    = "GrantGeographicInferenceProfile${substr(sha256(profile_key), 0, 12)}ModelAccess"
          Effect = "Allow"
          Action = "bedrock:InvokeModel"
          Resource = sort(tolist(
            var.bedrock_geographic_inference_profiles[profile_key].destination_foundation_model_arns,
          ))
          Condition = {
            StringEquals = {
              "bedrock:InferenceProfileArn" = var.bedrock_geographic_inference_profiles[profile_key].inference_profile_arn
            }
          }
        },
      ]
    ]),
  )

  cell_bedrock_policy_json = templatefile(
    "${path.module}/policies/cell-bedrock-policy.json.tftpl",
    {
      bedrock_invoke_model_statements_json = jsonencode(
        local.bedrock_invoke_model_statements,
      )
    },
  )
  fan_in_storage_policy_json = templatefile(
    "${path.module}/policies/fan-in-storage-policy.json.tftpl",
    {
      artifacts_kms_key_arn = var.artifacts_kms_key_arn
      results_bucket_arn    = local.results_bucket_arn
    },
  )
  prepare_inputs_storage_policy_json = templatefile(
    "${path.module}/policies/prepare-inputs-storage-policy.json.tftpl",
    {
      artifacts_kms_key_arn = var.artifacts_kms_key_arn
      results_bucket_arn    = local.results_bucket_arn
    },
  )
  # Create-only, and deliberately without any s3:ListBucket grant: staging reads
  # and writes every object by exact key, so a list grant would only widen what a
  # compromised run could enumerate.
  manifest_staging_storage_policy_json = templatefile(
    "${path.module}/policies/manifest-staging-policy.json.tftpl",
    {
      artifacts_kms_key_arn = var.artifacts_kms_key_arn
      packet_bucket_arn     = local.packet_bucket_arn
      results_bucket_arn    = local.results_bucket_arn
    },
  )
}
