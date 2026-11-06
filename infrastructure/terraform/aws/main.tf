locals {
  public_cidrs  = [for i in range(2) : cidrsubnet(var.vpc_cidr, 8, i)]
  private_cidrs = [for i in range(2) : cidrsubnet(var.vpc_cidr, 8, i + 10)]
}

data "aws_caller_identity" "current" {}

resource "aws_vpc" "router" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = var.name }
}

resource "aws_internet_gateway" "router" {
  vpc_id = aws_vpc.router.id
  tags   = { Name = var.name }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.router.id
  availability_zone       = var.availability_zones[count.index]
  cidr_block              = local.public_cidrs[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.name}-public-${count.index + 1}" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.router.id
  availability_zone = var.availability_zones[count.index]
  cidr_block        = local.private_cidrs[count.index]
  tags              = { Name = "${var.name}-private-${count.index + 1}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.router.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.router.id
  }
  tags = { Name = "${var.name}-public" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Starter topology uses one NAT gateway; use one per AZ for higher availability.
resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "${var.name}-nat" }
}

resource "aws_nat_gateway" "router" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  depends_on    = [aws_internet_gateway.router]
  tags          = { Name = var.name }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.router.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.router.id
  }
  tags = { Name = "${var.name}-private" }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "alb" {
  name        = "${var.name}-alb"
  description = "Internal router ALB"
  vpc_id      = aws_vpc.router.id

  ingress {
    description = "HTTP from the VPC"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  egress {
    description = "Router tasks in the VPC"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  tags = { Name = "${var.name}-alb" }
}

resource "aws_security_group" "task" {
  name        = "${var.name}-task"
  description = "Router Fargate tasks"
  vpc_id      = aws_vpc.router.id

  ingress {
    description     = "Internal ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    description = "AWS services and configured model APIs"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.name}-task" }
}

resource "aws_lb" "router" {
  name               = var.name
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.private[*].id
  tags               = { Name = var.name }
}

resource "aws_lb_target_group" "router" {
  name        = var.name
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.router.id

  health_check {
    path    = "/health/ready"
    matcher = "200"
  }
  tags = { Name = var.name }
}

resource "aws_lb_listener" "router" {
  load_balancer_arn = aws_lb.router.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.router.arn
  }
}

resource "aws_ecr_repository" "router" {
  name                 = var.name
  image_tag_mutability = "IMMUTABLE"

  encryption_configuration {
    encryption_type = "AES256"
  }
  tags = { Name = var.name }
}

resource "aws_cloudwatch_log_group" "router" {
  name              = "/ecs/${var.name}"
  retention_in_days = 30
  tags              = { Name = var.name }
}

resource "aws_iam_role" "execution" {
  name = "${var.name}-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        ArnLike      = { "aws:SourceArn" = "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*" }
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "provider_secret" {
  count = var.provider_api_key_secret_arn == null ? 0 : 1
  name  = "provider-secret"
  role  = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = var.provider_api_key_secret_arn
    }]
  })
}

resource "aws_ecs_cluster" "router" {
  name = var.name
  tags = { Name = var.name }
}

resource "aws_ecs_task_definition" "router" {
  family                   = var.name
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
    environment = [{ name = "ROUTER_MODELS_CONFIG", value = var.models_config_path }]
    secrets = var.provider_api_key_secret_arn == null ? [] : [{
      name      = var.provider_api_key_env
      valueFrom = var.provider_api_key_secret_arn
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.router.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "router"
      }
    }
    healthCheck = {
      command  = ["CMD-SHELL", "python -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8000/health/ready\", timeout=2)'"]
      interval = 30
      timeout  = 5
      retries  = 3
    }
  }])
  tags = { Name = var.name }
}

resource "aws_ecs_service" "router" {
  count           = var.deploy_service ? 1 : 0
  name            = var.name
  cluster         = aws_ecs_cluster.router.id
  task_definition = aws_ecs_task_definition.router.arn
  desired_count   = var.desired_count
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

  health_check_grace_period_seconds = 60
  depends_on                        = [aws_lb_listener.router, aws_iam_role_policy_attachment.execution, aws_iam_role_policy.provider_secret]
  tags                              = { Name = var.name }
}
