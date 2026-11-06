mock_provider "aws" {}

run "phase1_resources" {
  command = plan

  assert {
    condition     = aws_s3_bucket.router_artifacts.bucket == "enterprise-ai-router-artifacts-local"
    error_message = "Phase 1 must create the isolated LocalStack artifact bucket."
  }

  assert {
    condition     = aws_ecr_repository.router.name == "enterprise-ai-router" && aws_ecr_repository.router.image_tag_mutability == "MUTABLE"
    error_message = "Phase 1 must create the requested ECR repository."
  }

  assert {
    condition     = aws_secretsmanager_secret.router.name == "enterprise-ai-router/local/provider-config"
    error_message = "Phase 1 must create only the named secret container."
  }
}
