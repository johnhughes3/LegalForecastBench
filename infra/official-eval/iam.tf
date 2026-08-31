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

resource "aws_iam_role_policy" "cell_provider_authority" {
  name   = "official-eval-cell-exact-provider-authority"
  role   = aws_iam_role.cell.id
  policy = local.cell_provider_authority_policy_json

  lifecycle {
    precondition {
      condition = (
        local.computed_provider_authority_resource_identity_sha256 ==
        var.provider_authority_resource_identity_sha256
      )
      error_message = "provider authority table ARN differs from the frozen resource identity."
    }

    precondition {
      condition = (
        split(":", var.provider_authority_table_arn)[1] ==
        split(":", var.github_oidc_provider_arn)[1] &&
        split(":", var.provider_authority_table_arn)[3] == var.aws_region &&
        split(":", var.provider_authority_table_arn)[4] ==
        split(":", var.github_oidc_provider_arn)[4]
      )
      error_message = "provider authority table must use the configured AWS partition, region, and account."
    }
  }
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
    [
      aws_iam_role_policy.cell_storage.name,
      aws_iam_role_policy.cell_provider_authority.name,
    ],
    var.enable_bedrock_runtime ? [aws_iam_role_policy.cell_bedrock[0].name] : [],
  )
}

resource "aws_iam_role_policy_attachments_exclusive" "cell" {
  role_name   = aws_iam_role.cell.name
  policy_arns = []
}

# Prepare-inputs is intentionally a distinct read-only role. The forecast
# workflow uses it before provider cells run; it must not inherit the cell's
# marker writes or provider-authority DynamoDB access.
resource "aws_iam_role" "prepare_inputs" {
  name                 = "${var.name_prefix}-prepare-inputs"
  assume_role_policy   = local.prepare_inputs_trust_policy_json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "prepare_inputs_storage" {
  name   = "official-eval-prepare-inputs-storage"
  role   = aws_iam_role.prepare_inputs.id
  policy = local.prepare_inputs_storage_policy_json
}

resource "aws_iam_role_policies_exclusive" "prepare_inputs" {
  role_name    = aws_iam_role.prepare_inputs.name
  policy_names = [aws_iam_role_policy.prepare_inputs_storage.name]
}

resource "aws_iam_role_policy_attachments_exclusive" "prepare_inputs" {
  role_name   = aws_iam_role.prepare_inputs.name
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

# Staging is the only lane that creates manifest-run objects, so it gets its own
# role rather than a widened cell or fan-in grant: the cell must not be able to
# create objects in the prefix backing its own dispatched shards, and fan-in must
# not be able to create the inputs it later attests to.
resource "aws_iam_role" "manifest_staging" {
  name                 = "${var.name_prefix}-manifest-staging"
  assume_role_policy   = local.manifest_staging_trust_policy_json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "manifest_staging_storage" {
  name   = "official-eval-manifest-staging-storage"
  role   = aws_iam_role.manifest_staging.id
  policy = local.manifest_staging_storage_policy_json
}

resource "aws_iam_role_policies_exclusive" "manifest_staging" {
  role_name    = aws_iam_role.manifest_staging.name
  policy_names = [aws_iam_role_policy.manifest_staging_storage.name]
}

resource "aws_iam_role_policy_attachments_exclusive" "manifest_staging" {
  role_name   = aws_iam_role.manifest_staging.name
  policy_arns = []
}
