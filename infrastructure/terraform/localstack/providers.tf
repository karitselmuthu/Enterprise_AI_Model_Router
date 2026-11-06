provider "aws" {
  region     = "us-east-1"
  access_key = "test"
  secret_key = "test"

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = false
  skip_region_validation      = true

  endpoints {
    s3             = "http://localhost:4566"
    s3control      = "http://localhost.localstack.cloud:4566"
    ecr            = "http://localhost:4566"
    secretsmanager = "http://localhost:4566"
    sts            = "http://localhost:4566"
  }

  s3_use_path_style = true

  allowed_account_ids = ["000000000000"]
}
