# Override defaults here as needed.
project     = "budgetbot"
region      = "ap-southeast-1"
aws_profile = "default"

domain_root   = "budgetbot.xbrain26hackathon269.software"
app_subdomain = ""    # apex → budgetbot.xbrain26hackathon269.software (frontend / CloudFront)
api_subdomain = "api" # → api.budgetbot.xbrain26hackathon269.software (API / ALB)

ai_backend  = "bedrock"
pdf_backend = "bedrock"
# Anthropic use-case form submitted → Claude enabled account-wide.
# Verified working: Haiku 4.5, Sonnet 4.6, Opus 4.6.
ai_model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
# Alternatives (verified): "global.anthropic.claude-sonnet-4-6"
#                          "global.anthropic.claude-opus-4-6-v1"
#                          "apac.amazon.nova-lite-v1:0"  (cheapest, no form)

desired_count = 2 # initial; autoscaling manages within [backend_min,backend_max]
task_cpu      = 512
task_memory   = 1024

# Claude Haiku 4.5 list price (USD / 1M tokens) — for the cost report.
bedrock_input_cost_per_1m  = 1.0
bedrock_output_cost_per_1m = 5.0
