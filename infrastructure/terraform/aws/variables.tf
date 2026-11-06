variable "aws_region" {
  description = "AWS Region for the deployment."
  type        = string
  default     = "ap-south-1"
}

variable "name" {
  description = "Short name used to identify resources."
  type        = string
  default     = "enterprise-ai-router"
}

variable "vpc_cidr" {
  description = "VPC address range."
  type        = string
  default     = "10.42.0.0/16"
}

variable "availability_zones" {
  description = "Two availability zones in the selected Region."
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]

  validation {
    condition     = length(var.availability_zones) == 2 && var.availability_zones[0] != var.availability_zones[1]
    error_message = "Provide two distinct availability zones."
  }
}

variable "image_tag" {
  description = "Immutable ECR image tag to deploy after pushing the image."
  type        = string
  default     = "initial"
}

variable "deploy_service" {
  description = "Enable only after the image exists in ECR."
  type        = bool
  default     = false
}

variable "desired_count" {
  description = "Number of router tasks when the service is enabled."
  type        = number
  default     = 1

  validation {
    condition     = var.desired_count >= 1
    error_message = "desired_count must be at least one."
  }
}

variable "models_config_path" {
  description = "Path to a non-secret YAML configuration baked into the image."
  type        = string
  default     = "/app/configs/models.yaml"
}

variable "provider_api_key_env" {
  description = "Environment variable expected by the configured LiteLLM provider."
  type        = string
  default     = "OPENAI_API_KEY"
}

variable "provider_api_key_secret_arn" {
  description = "Existing Secrets Manager secret ARN; leave null for mock providers."
  type        = string
  default     = null
}
