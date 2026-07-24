output "packet_read_role_arn" {
  description = "Set as LFB_GITHUB_PACKET_READ_ROLE_ARN in legalforecastbench-official-eval."
  value       = aws_iam_role.cell.arn
}

output "fan_in_role_arn" {
  description = "Set as LFB_GITHUB_FAN_IN_ROLE_ARN in legalforecastbench-official-eval-fan-in."
  value       = aws_iam_role.fan_in.arn
}

output "packet_bucket_name" {
  description = "Set as LFB_PACKET_BUCKET in both protected environments."
  value       = aws_s3_bucket.packet.id
}

output "results_bucket_name" {
  description = "Set as LFB_RESULTS_BUCKET in both protected environments."
  value       = aws_s3_bucket.results.id
}

output "trusted_oidc_subjects" {
  description = "Exact environment-bound GitHub OIDC subjects admitted by the two roles."
  value = {
    cell   = local.cell_subject
    fan_in = local.fan_in_subject
  }
}
