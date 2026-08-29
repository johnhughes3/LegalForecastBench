output "packet_read_role_arn" {
  description = "Set as LFB_GITHUB_PACKET_READ_ROLE_ARN in legalforecastbench-official-eval."
  value       = aws_iam_role.cell.arn
}

output "fan_in_role_arn" {
  description = "Set as LFB_GITHUB_FAN_IN_ROLE_ARN in legalforecastbench-official-eval-fan-in."
  value       = aws_iam_role.fan_in.arn
}

output "manifest_staging_role_arn" {
  description = "Set as LFB_GITHUB_MANIFEST_STAGING_ROLE_ARN in legalforecastbench-official-eval-manifest-staging."
  value       = aws_iam_role.manifest_staging.arn
}

output "provider_authority_table_name" {
  description = "Set as LFB_PROVIDER_AUTHORITY_TABLE in legalforecastbench-official-eval."
  value       = split("/", var.provider_authority_table_arn)[1]
}

output "provider_authority_resource_identity_sha256" {
  description = "Commit this exact value in the frozen provider-cycle-caps artifact."
  value       = local.computed_provider_authority_resource_identity_sha256
}

output "packet_bucket_name" {
  description = "Verified external packet bucket name consumed by the IAM contract; set as LFB_PACKET_BUCKET in both protected environments."
  value       = var.packet_bucket_name
}

output "results_bucket_name" {
  description = "Verified external results bucket name consumed by the IAM contract; set as LFB_RESULTS_BUCKET in both protected environments."
  value       = var.results_bucket_name
}

output "trusted_oidc_subjects" {
  description = "Exact environment-bound GitHub OIDC subjects admitted by the three roles."
  value = {
    cell             = local.cell_subject
    fan_in           = local.fan_in_subject
    manifest_staging = local.manifest_staging_subject
  }
}
