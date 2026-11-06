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
    error_message = "Phase 1 must create the named secret container."
  }

  assert {
    condition     = jsondecode(aws_secretsmanager_secret_version.router_test.secret_string).OPENAI_API_KEY == "localstack-test-only"
    error_message = "The local secret must contain only the fake test credential."
  }
}

run "phase2_container" {
  command = plan

  assert {
    condition     = aws_ecs_task_definition.router.network_mode == "awsvpc" && aws_ecs_service.router.desired_count == 1
    error_message = "The router must have a running Fargate service."
  }

}
