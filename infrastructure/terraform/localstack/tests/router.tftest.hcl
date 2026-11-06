mock_provider "aws" {}

run "local_resources" {
  command = plan

  assert {
    condition     = aws_ecr_repository.router.image_tag_mutability == "IMMUTABLE"
    error_message = "The local registry should match the AWS immutable-tag rule."
  }

  assert {
    condition     = aws_s3_bucket.router_artifacts.bucket == "${var.name}-artifacts-local"
    error_message = "The artifact bucket should use the configured local name."
  }

  assert {
    condition     = aws_secretsmanager_secret.router.name == "${var.name}/local/provider-config"
    error_message = "The local secret should stay in its own namespace."
  }

  assert {
    condition     = length(aws_ecs_service.router) == 0
    error_message = "The local service must wait until an image is available."
  }
}

run "local_service" {
  command = plan

  variables {
    deploy_service = true
    image_tag      = "test-build"
  }

  assert {
    condition     = length(aws_ecs_service.router) == 1 && aws_ecs_task_definition.router.network_mode == "awsvpc"
    error_message = "The local ECS service must use the configured Fargate task."
  }
}
