resource "aws_iam_role" "cell" {
  name                 = var.name_prefix
  assume_role_policy   = local.cell_trust_policy_json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "cell_storage" {
  name   = "official-eval-cell-storage"
  role   = aws_iam_role.cell.id
  policy = local.cell_storage_policy_json
}

resource "aws_iam_role_policy" "cell_bedrock" {
  count = var.enable_bedrock_runtime ? 1 : 0

  name   = "official-eval-cell-bedrock-invoke"
  role   = aws_iam_role.cell.id
  policy = local.cell_bedrock_policy_json

  lifecycle {
    precondition {
      condition = (
        length(var.bedrock_direct_foundation_model_arns) > 0 ||
        length(var.bedrock_geographic_inference_profiles) > 0
      )
      error_message = "enable_bedrock_runtime requires an exact reviewed direct foundation model or geographic inference profile contract."
    }
  }
}

resource "aws_iam_role_policies_exclusive" "cell" {
  role_name = aws_iam_role.cell.name
  policy_names = concat(
    [aws_iam_role_policy.cell_storage.name],
    var.enable_bedrock_runtime ? [aws_iam_role_policy.cell_bedrock[0].name] : [],
  )
}

resource "aws_iam_role_policy_attachments_exclusive" "cell" {
  role_name   = aws_iam_role.cell.name
  policy_arns = []
}

resource "aws_iam_role" "fan_in" {
  name                 = "${var.name_prefix}-fan-in"
  assume_role_policy   = local.fan_in_trust_policy_json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "fan_in_storage" {
  name   = "official-eval-fan-in-storage"
  role   = aws_iam_role.fan_in.id
  policy = local.fan_in_storage_policy_json
}

resource "aws_iam_role_policies_exclusive" "fan_in" {
  role_name    = aws_iam_role.fan_in.name
  policy_names = [aws_iam_role_policy.fan_in_storage.name]
}

resource "aws_iam_role_policy_attachments_exclusive" "fan_in" {
  role_name   = aws_iam_role.fan_in.name
  policy_arns = []
}
