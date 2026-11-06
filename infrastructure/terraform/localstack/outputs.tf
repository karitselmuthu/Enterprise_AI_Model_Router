output "s3_bucket_name" {
  value = aws_s3_bucket.router_artifacts.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.router.repository_url
}

output "secret_arn" {
  value = aws_secretsmanager_secret.router.arn
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.router.name
}

output "ecs_service_name" {
  value = aws_ecs_service.router.name
}

output "alb_dns_name" {
  value = aws_lb.router.dns_name
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.router.name
}
