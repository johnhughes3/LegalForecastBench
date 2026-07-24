locals {
  labeling_subjects = sort([
    for environment_name in var.labeling_environment_names :
    "${var.github_subject_prefix}:environment:${environment_name}"
  ])
  computed_provider_authority_resource_identity_sha256 = sha256(
    var.provider_authority_table_arn
  )
}

data "aws_iam_policy_document" "labeling_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.labeling_subjects
    }
  }
}

resource "aws_iam_role" "labeling" {
  name                 = "${var.name_prefix}-authority"
  assume_role_policy   = data.aws_iam_policy_document.labeling_trust.json
  max_session_duration = 7200
  tags                 = var.tags

  lifecycle {
    precondition {
      condition = (
        local.computed_provider_authority_resource_identity_sha256 ==
        var.provider_authority_resource_identity_sha256
      )
      error_message = "provider authority table ARN differs from the frozen resource identity."
    }
  }
}

data "aws_iam_policy_document" "labeling" {
  statement {
    sid    = "ExactProviderAuthorityDataPlane"
    effect = "Allow"
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:TransactWriteItems",
      "dynamodb:UpdateItem",
    ]
    resources = [var.provider_authority_table_arn]
  }
}

resource "aws_iam_role_policy" "labeling" {
  name   = "official-labeling-exact-provider-authority"
  role   = aws_iam_role.labeling.id
  policy = data.aws_iam_policy_document.labeling.json
}
