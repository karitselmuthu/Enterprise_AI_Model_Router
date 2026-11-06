variable "aws_region" {
  description = "Emulated AWS Region."
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Prefix for local test resources."
  type        = string
  default     = "enterprise-ai-router"
}

variable "deploy_service" {
  description = "Enable after pushing a local ECR image."
  type        = bool
  default     = false
}

variable "image_tag" {
  description = "Tag of the image pushed to LocalStack ECR."
  type        = string
  default     = "initial"
}
