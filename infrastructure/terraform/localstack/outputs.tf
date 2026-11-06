output "s3_bucket_name" {
  value = aws_s3_bucket.router_artifacts.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.router.repository_url
}

output "secret_arn" {
  value = aws_secretsmanager_secret.router.arn
}
