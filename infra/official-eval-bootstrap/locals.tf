locals {
  account_id            = data.aws_caller_identity.current.account_id
  partition             = data.aws_partition.current.partition
  dns_suffix            = data.aws_partition.current.dns_suffix
  state_bucket_arn      = "arn:${local.partition}:s3:::${var.state_bucket_name}"
  account_root_arn      = "arn:${local.partition}:iam::${local.account_id}:root"
  operator_role_arn     = "arn:${local.partition}:iam::${local.account_id}:role/${var.operator_role_name}"
  github_provider_arn   = "arn:${local.partition}:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"
  provider_table_arn    = "arn:${local.partition}:dynamodb:${var.aws_region}:${local.account_id}:table/${var.provider_authority_table_name}"
  official_labeling_arn = "arn:${local.partition}:iam::${local.account_id}:role/${var.official_labeling_role_name}"
  kms_via_service       = "s3.${var.aws_region}.${local.dns_suffix}"

  provider_authority_state_key = (
    "${var.state_key_prefix}/provider-authority/terraform.tfstate"
  )
  official_labeling_state_key = (
    "${var.state_key_prefix}/official-labeling/terraform.tfstate"
  )
  github_ref     = "refs/heads/main"
  github_subject = "repo:${var.github_repository}:environment:${var.github_environment}"

  operator_trust_policy = templatefile(
    "${path.module}/policies/github-oidc-trust.json.tftpl",
    {
      github_oidc_provider_arn = local.github_provider_arn
      github_repository        = var.github_repository
      github_ref               = local.github_ref
      github_environment       = var.github_environment
      github_subject           = local.github_subject
    },
  )
  operator_policy = templatefile(
    "${path.module}/policies/operator-policy.json.tftpl",
    {
      state_bucket_arn             = local.state_bucket_arn
      provider_authority_state_key = local.provider_authority_state_key
      official_labeling_state_key  = local.official_labeling_state_key
      kms_key_arn                  = aws_kms_key.terraform_state.arn
      kms_via_service              = local.kms_via_service
      provider_authority_table_arn = local.provider_table_arn
      official_labeling_role_arn   = local.official_labeling_arn
    },
  )
  kms_key_policy = templatefile(
    "${path.module}/policies/kms-key-policy.json.tftpl",
    {
      account_root_arn  = local.account_root_arn
      operator_role_arn = local.operator_role_arn
      kms_via_service   = local.kms_via_service
      state_bucket_arn  = local.state_bucket_arn
    },
  )
}
