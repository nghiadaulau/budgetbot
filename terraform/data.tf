data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_route53_zone" "main" {
  name         = "${var.domain_root}."
  private_zone = false
}

locals {
  azs          = slice(data.aws_availability_zones.available.names, 0, 2)
  app_fqdn     = var.app_subdomain == "" ? var.domain_root : "${var.app_subdomain}.${var.domain_root}"
  api_fqdn     = "${var.api_subdomain}.${var.domain_root}"
  name         = var.project
  cors_origins = "https://${local.app_fqdn}"
}
