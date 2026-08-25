data "aws_iam_openid_connect_provider" "github_actions" {
  arn = var.github_oidc_provider_arn
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
        var.github_oidc_provider_arn == local.github_provider_arn
      )
      error_message = "GitHub OIDC provider must belong to the current AWS account and partition."
    }

    precondition {
      condition = (
        data.aws_iam_openid_connect_provider.github_actions.url ==
        "token.actions.githubusercontent.com" &&
        toset(data.aws_iam_openid_connect_provider.github_actions.client_id_list) ==
        toset(["sts.amazonaws.com"])
      )
      error_message = "Existing GitHub OIDC provider must use token.actions.githubusercontent.com with only the sts.amazonaws.com audience."
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
