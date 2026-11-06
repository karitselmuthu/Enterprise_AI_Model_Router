provider "aws" {
  region     = "us-east-1"
  access_key = "test"
  secret_key = "test"

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = false
  skip_region_validation      = true

  endpoints {
    s3                     = var.localstack_endpoint
    s3control              = var.localstack_endpoint
    ecr                    = var.localstack_endpoint
    ec2                    = var.localstack_endpoint
    ecs                    = var.localstack_endpoint
    elasticloadbalancing   = var.localstack_endpoint
    elasticloadbalancingv2 = var.localstack_endpoint
    iam                    = var.localstack_endpoint
    secretsmanager         = var.localstack_endpoint
    sts                    = var.localstack_endpoint
  }

  s3_use_path_style = true

  allowed_account_ids = ["000000000000"]
}
