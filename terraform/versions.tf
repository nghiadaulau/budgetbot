terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "s3" {
    bucket       = "budgetbot-tfstate-xbrain26hackathon269"
    key          = "budgetbot/terraform.tfstate"
    region       = "ap-southeast-1"
    profile      = "default"
    encrypt      = true
    use_lockfile = true
  }
}
