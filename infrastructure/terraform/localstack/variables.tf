variable "localstack_endpoint" {
  description = "Approved LocalStack endpoint for local AWS emulation."
  type        = string
  default     = "http://localhost:4566"

  validation {
    condition = contains([
      "http://localhost:4566",
      "http://127.0.0.1:4566",
      "http://localhost.localstack.cloud:4566"
    ], var.localstack_endpoint)

    error_message = "LocalStack endpoint must use the approved local port 4566."
  }
}
variable "image_tag" {
  description = "Tag already pushed to the LocalStack ECR repository."
  type        = string
  default     = "phase4-283f196"
}
