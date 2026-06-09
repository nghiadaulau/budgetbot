variable "project" {
  type        = string
  default     = "budgetbot"
  description = "Name prefix for all resources."
}

variable "region" {
  type        = string
  default     = "ap-southeast-1"
  description = "AWS region for the app (Fargate, ALB, RDS, ElastiCache, ECR)."
}

variable "aws_profile" {
  type        = string
  default     = "default"
  description = "Local AWS CLI profile used by Terraform and the deploy scripts."
}

variable "domain_root" {
  type        = string
  default     = "budgetbot.xbrain26hackathon269.software"
  description = "Route53 public hosted zone (created via CLI; delegate NS from the parent)."
}

variable "app_subdomain" {
  type        = string
  default     = ""
  description = "Frontend host. Empty = apex; else <app_subdomain>.<domain_root> (CloudFront)."
}

variable "api_subdomain" {
  type        = string
  default     = "api"
  description = "API host → <api_subdomain>.<domain_root> (ALB)."
}

variable "image_tag" {
  type        = string
  default     = "latest"
  description = "Backend image tag in ECR (pushed by deploy.sh)."
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "task_cpu" {
  type    = number
  default = 512
}

variable "task_memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  type        = number
  default     = 2
  description = "Initial backend task count (state is RDS now; autoscaling adjusts within min/max)."
}

variable "ai_backend" {
  type    = string
  default = "bedrock"
}

variable "pdf_backend" {
  type    = string
  default = "bedrock"
}

variable "ai_model_id" {
  type    = string
  default = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "bedrock_input_cost_per_1m" {
  type    = number
  default = 1.0
}

variable "bedrock_output_cost_per_1m" {
  type    = number
  default = 5.0
}

variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "db_engine_version" {
  type    = string
  default = "16"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_multi_az" {
  type    = bool
  default = false
}

variable "db_backup_retention_days" {
  type    = number
  default = 1
}

variable "worker_count" {
  type    = number
  default = 1
}

variable "uploads_retention_days" {
  type    = number
  default = 7
}

variable "valkey_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "valkey_engine_version" {
  type    = string
  default = "8.0"
}

variable "rate_limit_per_minute" {
  type    = number
  default = 60
}

variable "backend_min_count" {
  type    = number
  default = 2
}

variable "backend_max_count" {
  type    = number
  default = 6
}

variable "worker_min_count" {
  type    = number
  default = 1
}

variable "worker_max_count" {
  type    = number
  default = 4
}

variable "autoscale_cpu_target" {
  type    = number
  default = 65
}

variable "alarm_email" {
  type        = string
  default     = ""
  description = "Optional email subscribed to the CloudWatch alarm SNS topic."
}

variable "waf_rate_limit_per_5min" {
  type        = number
  default     = 2000
  description = "Per-IP request cap over a 5-minute window (WAF rate-based rule)."
}
