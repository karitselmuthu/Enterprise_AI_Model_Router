provider "aws" {
  region     = var.aws_region
  access_key = "test"
  secret_key = "test"

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  skip_region_validation      = true

  endpoints {
    s3             = "http://localhost:4566"
    ecr            = "http://localhost:4566"
    secretsmanager = "http://localhost:4566"
    ecs            = "http://localhost:4566"
    ec2            = "http://localhost:4566"
    iam            = "http://localhost:4566"
    logs           = "http://localhost:4566"
  }

  s3_use_path_style = true

  allowed_account_ids = ["000000000000"]
}
