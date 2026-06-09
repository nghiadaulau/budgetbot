
locals {
  app_env = [
    { name = "AI_BACKEND", value = var.ai_backend },
    { name = "PDF_BACKEND", value = var.pdf_backend },
    { name = "AI_MODEL_ID", value = var.ai_model_id },
    { name = "AWS_REGION", value = var.region },
    { name = "BEDROCK_INPUT_COST_PER_1M", value = tostring(var.bedrock_input_cost_per_1m) },
    { name = "BEDROCK_OUTPUT_COST_PER_1M", value = tostring(var.bedrock_output_cost_per_1m) },
    { name = "USERSTORE_BACKEND", value = "postgres" },
    { name = "DB_SECRET_NAME", value = aws_secretsmanager_secret.db.name },
    { name = "STORAGE_BACKEND", value = "s3" },
    { name = "STORAGE_BUCKET", value = aws_s3_bucket.uploads.bucket },
    { name = "SQS_QUEUE_URL", value = aws_sqs_queue.main.url },
    { name = "TEXTRACT_ENABLED", value = "true" },
    { name = "DEDUP_ENABLED", value = "true" },
    { name = "REQUIRE_AUTH", value = "true" },
    { name = "COGNITO_USER_POOL_ID", value = aws_cognito_user_pool.main.id },
    { name = "COGNITO_CLIENT_ID", value = aws_cognito_user_pool_client.spa.id },
    { name = "COGNITO_REGION", value = var.region },
    { name = "RATE_LIMIT_ENABLED", value = "true" },
    { name = "RATE_LIMIT_PER_MINUTE", value = tostring(var.rate_limit_per_minute) },
    { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.valkey.primary_endpoint_address}:6379" },
    { name = "APP_ENV", value = "prod" },
    { name = "LOG_LEVEL", value = "INFO" },
  ]
}

resource "aws_s3_bucket" "uploads" {
  bucket = "${local.name}-uploads-${data.aws_caller_identity.current.account_id}"
  tags   = { Name = "${local.name}-uploads" }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    id     = "expire-raw-uploads"
    status = "Enabled"
    filter {}
    expiration { days = var.uploads_retention_days }
  }
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${local.name}-jobs-dlq"
  message_retention_seconds = 1209600
  tags                      = { Name = "${local.name}-jobs-dlq" }
}

resource "aws_sqs_queue" "main" {
  name                       = "${local.name}-jobs"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 345600
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
  tags = { Name = "${local.name}-jobs" }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name}-worker"
  retention_in_days = 14
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name        = "worker"
    image       = "${aws_ecr_repository.backend.repository_url}:${var.image_tag}"
    essential   = true
    command     = ["python", "-m", "src.worker"]
    environment = local.app_env
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }

  depends_on = [aws_db_instance.main, aws_secretsmanager_secret_version.db]

  lifecycle {
    ignore_changes = [desired_count]
  }
}

output "uploads_bucket" {
  value = aws_s3_bucket.uploads.bucket
}

output "jobs_queue_url" {
  value = aws_sqs_queue.main.url
}
