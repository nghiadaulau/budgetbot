output "app_url" {
  description = "Frontend URL (CloudFront)"
  value       = "https://${local.app_fqdn}"
}

output "api_url" {
  description = "Backend API URL (ALB)"
  value       = "https://${local.api_fqdn}"
}

output "ecr_repository_url" {
  description = "Push the backend image here (deploy.sh)"
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_bucket" {
  description = "S3 bucket for the built frontend (deploy.sh syncs here)"
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_distribution_id" {
  description = "For cache invalidation after a frontend deploy"
  value       = aws_cloudfront_distribution.frontend.id
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service" {
  value = aws_ecs_service.backend.name
}

output "ecs_worker_service" {
  value = aws_ecs_service.worker.name
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}
