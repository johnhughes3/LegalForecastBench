variable "aws_region" {
  description = "AWS region containing the shared provider spend authority table."
  type        = string
  default     = "us-east-1"
}

variable "table_name" {
  description = "Stable name of the shared provider spend authority table."
  type        = string
  default     = "legalforecastbench-official-eval-provider-authority"

  validation {
    condition = (
      var.table_name == "legalforecastbench-official-eval-provider-authority"
    )
    error_message = "table_name must remain the reviewed shared authority table name."
  }
}

variable "tags" {
  description = "Additional non-sensitive AWS resource tags."
  type        = map(string)
  default     = {}
}
