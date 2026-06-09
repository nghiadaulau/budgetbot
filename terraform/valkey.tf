
resource "aws_elasticache_subnet_group" "valkey" {
  name       = "${local.name}-valkey"
  subnet_ids = aws_subnet.public[*].id
}

resource "aws_security_group" "valkey" {
  name        = "${local.name}-valkey"
  description = "Valkey access from the ECS task only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Valkey/Redis from ECS task"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.task.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-valkey" }
}

resource "aws_elasticache_replication_group" "valkey" {
  replication_group_id       = "${local.name}-valkey"
  description                = "BudgetBot rate-limit store (Valkey)"
  engine                     = "valkey"
  engine_version             = var.valkey_engine_version
  node_type                  = var.valkey_node_type
  num_cache_clusters         = 1
  automatic_failover_enabled = false
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.valkey.name
  security_group_ids         = [aws_security_group.valkey.id]
  transit_encryption_enabled = false
  apply_immediately          = true

  tags = { Name = "${local.name}-valkey" }
}

output "valkey_endpoint" {
  value = aws_elasticache_replication_group.valkey.primary_endpoint_address
}
