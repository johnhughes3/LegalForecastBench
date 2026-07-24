resource "aws_dynamodb_table" "provider_authority" {
  name         = var.table_name
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

  deletion_protection_enabled = true

  point_in_time_recovery {
    enabled = true
  }

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
      Purpose = "LegalForecastBench shared provider spend authority"
    },
  )

  lifecycle {
    prevent_destroy = true
  }
}
