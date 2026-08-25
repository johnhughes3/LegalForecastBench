output "state_bucket_name" {
  description = "Protected Terraform state bucket name."
  value       = aws_s3_bucket.terraform_state.id
  sensitive   = true
}

output "state_kms_key_arn" {
  description = "Exact customer-managed key ARN for backend configuration."
  value       = aws_kms_key.terraform_state.arn
  sensitive   = true
}

output "github_oidc_provider_arn" {
  description = "Account-level GitHub Actions OIDC provider ARN."
  value       = data.aws_iam_openid_connect_provider.github_actions.arn
  sensitive   = true
}

output "operator_role_arn" {
  description = "Exact protected-workflow operator role ARN."
  value       = aws_iam_role.operator.arn
  sensitive   = true
}

output "bootstrap_state_key" {
  description = "Human-controlled remote key for this bootstrap root."
  value       = var.bootstrap_state_key
  sensitive   = true
}
