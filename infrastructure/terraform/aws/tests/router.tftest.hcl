mock_provider "aws" {}

run "safe_first_apply" {
  command = plan

  assert {
    condition     = aws_lb.router.internal && length(aws_ecs_service.router) == 0
    error_message = "The starter plan must use a private load balancer and leave the service disabled."
  }

  assert {
    condition     = aws_ecr_repository.router.image_tag_mutability == "IMMUTABLE"
    error_message = "Published images must use immutable tags."
  }
}

run "private_service" {
  command = plan

  variables {
    deploy_service = true
    image_tag      = "test-build"
  }

  assert {
    condition     = length(aws_ecs_service.router) == 1 && !aws_ecs_service.router[0].network_configuration[0].assign_public_ip
    error_message = "An enabled service must run without a public task IP."
  }

  assert {
    condition     = aws_lb_target_group.router.health_check[0].path == "/health/ready"
    error_message = "The target group must check the router readiness path."
  }
}
