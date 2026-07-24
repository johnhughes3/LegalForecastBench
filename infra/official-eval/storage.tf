resource "aws_s3_bucket" "packet" {
  bucket        = var.packet_bucket_name
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "results" {
  bucket        = var.results_bucket_name
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "packet" {
  bucket = aws_s3_bucket.packet.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "results" {
  bucket = aws_s3_bucket.results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "packet" {
  bucket = aws_s3_bucket.packet.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_ownership_controls" "results" {
  bucket = aws_s3_bucket.results.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "packet" {
  bucket = aws_s3_bucket.packet.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "results" {
  bucket = aws_s3_bucket.results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "packet" {
  bucket = aws_s3_bucket.packet.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "results" {
  bucket = aws_s3_bucket.results.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "packet" {
  bucket = aws_s3_bucket.packet.id

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "results" {
  bucket = aws_s3_bucket.results.id

  depends_on = [aws_s3_bucket_versioning.results]

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "expire-disposable-security-negative-controls"
    status = "Enabled"

    filter {
      prefix = "reports/security-negative-controls/"
    }

    expiration {
      days = var.negative_control_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.negative_control_retention_days
    }
  }
}

resource "aws_s3_bucket_policy" "packet" {
  bucket = aws_s3_bucket.packet.id
  policy = templatefile(
    "${path.module}/policies/tls-only-bucket-policy.json.tftpl",
    { bucket_arn = aws_s3_bucket.packet.arn },
  )
}

resource "aws_s3_bucket_policy" "results" {
  bucket = aws_s3_bucket.results.id
  policy = templatefile(
    "${path.module}/policies/tls-only-bucket-policy.json.tftpl",
    { bucket_arn = aws_s3_bucket.results.arn },
  )
}
