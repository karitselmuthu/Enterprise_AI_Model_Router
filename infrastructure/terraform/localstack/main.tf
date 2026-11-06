resource "aws_s3_bucket" "router_artifacts" {
  bucket = "enterprise-ai-router-artifacts-local"
}

resource "aws_ecr_repository" "router" {
  name = "enterprise-ai-router"

  image_tag_mutability = "MUTABLE"
}

resource "aws_secretsmanager_secret" "router" {
  name = "enterprise-ai-router/local/provider-config"
}
