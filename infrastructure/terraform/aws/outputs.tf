output "ecr_repository_url" {
  description = "Push an image here before enabling the ECS service."
  value       = aws_ecr_repository.router.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.router.name
}

output "internal_alb_dns_name" {
  description = "Reachable only from the VPC or a connected network."
  value       = aws_lb.router.dns_name
}

output "alb_listener_arn" {
  description = "Use for an optional API Gateway VPC Link private integration."
  value       = aws_lb_listener.router.arn
}

output "service_enabled" {
  value = var.deploy_service
}
