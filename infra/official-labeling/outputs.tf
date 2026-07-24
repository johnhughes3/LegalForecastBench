output "labeling_role_name" {
  description = "Protected paid-labeling role name."
  value       = aws_iam_role.labeling.name
}

output "labeling_role_arn" {
  description = "Protected paid-labeling role ARN. Keep this in protected environment configuration."
  value       = aws_iam_role.labeling.arn
  sensitive   = true
}

output "provider_authority_resource_identity_sha256" {
  description = "Public, non-secret identity committed by provider-cycle-caps."
  value       = local.computed_provider_authority_resource_identity_sha256
}
