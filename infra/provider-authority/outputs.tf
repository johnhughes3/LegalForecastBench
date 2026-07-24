output "provider_authority_table_name" {
  description = "Protected table name for paid-labeling environment configuration."
  value       = aws_dynamodb_table.provider_authority.name
  sensitive   = true
}

output "provider_authority_table_arn" {
  description = "Protected exact ARN consumed by the paid-labeling IAM module."
  value       = aws_dynamodb_table.provider_authority.arn
  sensitive   = true
}

output "provider_authority_resource_identity_sha256" {
  description = "Public digest frozen into provider-cycle-caps; the ARN itself remains protected."
  value       = sha256(aws_dynamodb_table.provider_authority.arn)
}
