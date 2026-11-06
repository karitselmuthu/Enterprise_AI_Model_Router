resource "aws_cloudwatch_log_group" "router" {
  name              = "/ecs/enterprise-ai-router-local"
  retention_in_days = 7
}
