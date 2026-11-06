resource "aws_vpc" "router" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "enterprise-ai-router-local" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.router.id
  availability_zone = ["us-east-1a", "us-east-1b"][count.index]
  cidr_block        = cidrsubnet(aws_vpc.router.cidr_block, 8, count.index + 10)
  tags              = { Name = "enterprise-ai-router-private-${count.index + 1}" }
}

resource "aws_security_group" "alb" {
  name        = "enterprise-ai-router-local-alb"
  description = "LocalStack router ALB"
  vpc_id      = aws_vpc.router.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.router.cidr_block]
  }
  egress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.router.cidr_block]
  }
}

resource "aws_security_group" "task" {
  name        = "enterprise-ai-router-local-task"
  description = "LocalStack router task"
  vpc_id      = aws_vpc.router.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "router" {
  name               = "enterprise-ai-router-local"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.private[*].id
}

resource "aws_lb_target_group" "router" {
  name        = "enterprise-ai-router-local"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.router.id

  health_check {
    path    = "/health/ready"
    matcher = "200"
  }
}

resource "aws_lb_listener" "router" {
  load_balancer_arn = aws_lb.router.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.router.arn
  }

  # LocalStack reports its gateway port (4566) when reading this listener.
  lifecycle {
    ignore_changes = [port]
  }
}

resource "aws_iam_role" "execution" {
  name = "enterprise-ai-router-local-execution"
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

resource "aws_iam_role_policy" "provider_secret" {
  name = "provider-secret"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = aws_secretsmanager_secret.router.arn
    }]
  })
}
