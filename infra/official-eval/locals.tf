locals {
  github_repository     = "johnhughes3/LegalForecastBench"
  github_ref            = "refs/heads/main"
  github_subject_prefix = "repo:${local.github_repository}"

  cell_environment_name   = "legalforecastbench-official-eval"
  fan_in_environment_name = "legalforecastbench-official-eval-fan-in"

  cell_subject = (
    "${local.github_subject_prefix}:environment:${local.cell_environment_name}"
  )
  fan_in_subject = (
    "${local.github_subject_prefix}:environment:${local.fan_in_environment_name}"
  )

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

  cell_storage_policy_json = templatefile(
    "${path.module}/policies/cell-storage-policy.json.tftpl",
    {
      packet_bucket_arn  = aws_s3_bucket.packet.arn
      results_bucket_arn = aws_s3_bucket.results.arn
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
      results_bucket_arn = aws_s3_bucket.results.arn
    },
  )
}
