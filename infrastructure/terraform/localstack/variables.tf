variable "image_tag" {
  description = "Tag already pushed to the LocalStack ECR repository."
  type        = string
  default     = "phase2-a9b8e16"
}

variable "localstack_endpoint" {
  type    = string
  default = "http://localhost:4566"

  validation {
    condition     = can(regex("^http://(localhost|127\\.0\\.0\\.1|localhost\\.localstack\\.cloud):[0-9]+$", var.localstack_endpoint))
    error_message = "LocalStack endpoint must use localhost on an explicit port."
  }
}
