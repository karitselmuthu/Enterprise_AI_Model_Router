resource "aws_s3_bucket" "router_artifacts" {
  bucket = "${var.name}-artifacts-local"
}

resource "aws_ecr_repository" "router" {
  name = var.name

  image_tag_mutability = "IMMUTABLE"
}

resource "aws_secretsmanager_secret" "router" {
  name = "${var.name}/local/provider-config"
}

resource "aws_vpc" "router" {
  cidr_block = "10.55.0.0/16"
  tags       = { Name = "${var.name}-local" }
}

resource "aws_subnet" "router" {
  vpc_id            = aws_vpc.router.id
  cidr_block        = "10.55.1.0/24"
  availability_zone = "${var.aws_region}a"
}

resource "aws_security_group" "router" {
  name   = "${var.name}-local"
  vpc_id = aws_vpc.router.id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_cloudwatch_log_group" "router" {
  name = "/ecs/${var.name}-local"
}

resource "aws_iam_role" "execution" {
  name = "${var.name}-local-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecs_cluster" "router" {
  name = "${var.name}-local"
}

resource "aws_ecs_task_definition" "router" {
  family                   = "${var.name}-local"
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
    environment = [{ name = "ROUTER_MODELS_CONFIG", value = "/app/configs/models.yaml" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.router.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "router"
      }
    }
  }])
}

resource "aws_ecs_service" "router" {
  count           = var.deploy_service ? 1 : 0
  name            = "${var.name}-local"
  cluster         = aws_ecs_cluster.router.id
  task_definition = aws_ecs_task_definition.router.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.router.id]
    security_groups  = [aws_security_group.router.id]
    assign_public_ip = false
  }

  depends_on = [aws_iam_role_policy_attachment.execution]
}
