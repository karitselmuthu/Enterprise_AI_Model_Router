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

resource "aws_ecs_cluster" "router" {
  name = "enterprise-ai-router-local"
}

resource "aws_ecs_task_definition" "router" {
  family                   = "enterprise-ai-router-local"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn

  container_definitions = jsonencode([{
    name      = "router"
    image     = "${aws_ecr_repository.router.repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    environment = [{
      name  = "ROUTER_MODELS_CONFIG"
      value = "/app/configs/models.yaml"
    }]
    secrets = [{
      name      = "OPENAI_API_KEY"
      valueFrom = "${aws_secretsmanager_secret.router.arn}:OPENAI_API_KEY::"
    }]
  }])
}

resource "aws_ecs_service" "router" {
  name            = "enterprise-ai-router-local"
  cluster         = aws_ecs_cluster.router.id
  task_definition = aws_ecs_task_definition.router.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.router.arn
    container_name   = "router"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.router]
}
