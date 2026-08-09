resource "aws_iam_openid_connect_provider" "github_actions" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  tags           = var.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role" "operator" {
  name                 = var.operator_role_name
  assume_role_policy   = local.operator_trust_policy
  max_session_duration = 3600
  tags                 = var.tags

  lifecycle {
    prevent_destroy = true

    precondition {
      condition = (
        aws_iam_openid_connect_provider.github_actions.arn ==
        local.github_provider_arn
      )
      error_message = "GitHub OIDC provider must belong to the current AWS account and partition."
    }
  }
}

resource "aws_iam_role_policy" "operator" {
  name   = "reviewed-lfb-terraform-roots"
  role   = aws_iam_role.operator.id
  policy = local.operator_policy
}

resource "aws_iam_role_policies_exclusive" "operator" {
  role_name    = aws_iam_role.operator.name
  policy_names = [aws_iam_role_policy.operator.name]
}

resource "aws_iam_role_policy_attachments_exclusive" "operator" {
  role_name   = aws_iam_role.operator.name
  policy_arns = []
}
