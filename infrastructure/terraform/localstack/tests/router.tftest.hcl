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

run "phase3_security_networking" {
  command = plan

  assert {
    condition     = aws_vpc.router.cidr_block == "10.42.0.0/16" && length(aws_subnet.private) == 2
    error_message = "The router needs a dedicated VPC and two subnets."
  }

  assert {
    condition     = aws_lb.router.internal && aws_lb_target_group.router.target_type == "ip"
    error_message = "The ALB must be internal and target ECS task IPs."
  }

  assert {
    condition     = aws_iam_role.execution.name == "enterprise-ai-router-local-execution" && anytrue([for lb in aws_ecs_service.router.load_balancer : lb.container_port == 8000])
    error_message = "ECS needs its execution role and ALB attachment."
  }
}

run "phase4_observability" {
  command = plan

  assert {
    condition     = aws_cloudwatch_log_group.router.retention_in_days == 7
    error_message = "ECS logs must have bounded retention."
  }
}
