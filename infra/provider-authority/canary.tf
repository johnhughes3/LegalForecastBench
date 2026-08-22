resource "aws_dynamodb_table" "outside_authority_canary" {
  name         = var.outside_authority_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "authority_key"
  range_key    = "record_key"

  attribute {
    name = "authority_key"
    type = "S"
  }

  attribute {
    name = "record_key"
    type = "S"
  }

  # This table is a disposable negative-control target for the permission smoke.
  # Keep deletion protection and point-in-time recovery off so it can be removed
  # after the smoke without retaining an unnecessary durable resource.
  deletion_protection_enabled = false

  server_side_encryption {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = merge(
    var.tags,
    {
      Purpose   = "Provider-free labeling authority negative control"
      Lifecycle = "disposable-canary"
    },
  )

  lifecycle {
    precondition {
      condition = (
        var.outside_authority_table_name != var.table_name
      )
      error_message = "The authority-smoke canary table must remain distinct from the shared authority table."
    }
  }
}
