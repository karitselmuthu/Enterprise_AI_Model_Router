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

# Deliberately fake credential for testing secret injection later. Never replace
# this literal with a real provider key; Terraform stores secret values in state.
resource "aws_secretsmanager_secret_version" "router_test" {
  secret_id = aws_secretsmanager_secret.router.id
  secret_string = jsonencode({
    OPENAI_API_KEY = "localstack-test-only"
  })
}
