# Terraform environments

These are **separate Terraform root configurations and state files**:

- `aws/` provisions a private ECS Fargate router, ECR, VPC networking, an
  internal ALB, CloudWatch logs, and an ECS execution role.
- `localstack/` is Phase 1 only: an S3 artifact bucket, ECR repository, and
  empty Secrets Manager secret against LocalStack Desktop. ECS belongs to a
  later phase and is deliberately absent from this configuration.

Neither configuration has been applied. Review `terraform plan` before any
`apply`; AWS NAT Gateway and ALB resources incur charges even when
`deploy_service = false`. Use a remote, encrypted state backend for team use;
the starter files use local state, which is ignored by Git. Do not place API
keys in `.tfvars` or commit state files.

## Real AWS

Prerequisites: an AWS account, a chosen Region, two valid Availability Zones,
AWS CLI credentials with provisioning permissions, Terraform, Docker with
`buildx`, and a model-provider API key if using LiteLLM. The `aws/` defaults
to `configs/models.yaml`, so it starts with mock providers. To use cloud models,
add a **non-secret** model YAML under `configs/` before building the image, set
`models_config_path` to its `/app/configs/...` path, and provide an existing
Secrets Manager secret ARN through `provider_api_key_secret_arn`. If that secret
uses a customer-managed KMS key, grant the execution role `kms:Decrypt` on it.

```bash
DEPLOY_PROFILE=my-aws-profile
aws sso login --profile "$DEPLOY_PROFILE"
aws sts get-caller-identity --profile "$DEPLOY_PROFILE"
export AWS_PROFILE="$DEPLOY_PROFILE"
terraform -chdir=infrastructure/terraform/aws init
terraform -chdir=infrastructure/terraform/aws plan
terraform -chdir=infrastructure/terraform/aws apply
```

The first apply creates ECR and networking, but no ECS service. After it
finishes, build for the Fargate Linux architecture, push an immutable tag, and
enable the service:

```bash
DEPLOY_REGION=ap-south-1
DEPLOY_REPO_URL=$(terraform -chdir=infrastructure/terraform/aws output -raw ecr_repository_url)
DEPLOY_TAG=build-001
aws ecr get-login-password --region "$DEPLOY_REGION" --profile "$DEPLOY_PROFILE" \
  | docker login --username AWS --password-stdin "${DEPLOY_REPO_URL%%/*}"
docker buildx build --platform linux/amd64 --build-arg INSTALL_PROVIDERS=true \
  -t "$DEPLOY_REPO_URL:$DEPLOY_TAG" --load .
docker push "$DEPLOY_REPO_URL:$DEPLOY_TAG"
terraform -chdir=infrastructure/terraform/aws apply \
  -var='deploy_service=true' -var="image_tag=$DEPLOY_TAG"
```

The ALB is internal and only accepts clients inside the VPC. Test from a
connected network, or add an authenticated API Gateway private integration
through a VPC Link. This Terraform does not provision API Gateway, a JWT
issuer, WAF, dashboards, alarms, or a remote state backend. The single NAT
Gateway is a starter dependency in one Availability Zone; plan a NAT per AZ
for higher availability. `/health/ready` checks application startup, not
model-provider credentials or connectivity. Verify `/v1/execute` separately.

## LocalStack Desktop

Prerequisites: Docker running, LocalStack Desktop or `lstk`, a LocalStack auth
token, and a LocalStack plan that includes ECR. The provider points the three
Phase 1 resource services at `http://localhost:4566`, uses dummy credentials,
and restricts the account ID to `000000000000`. STS is also mapped locally so
the provider can read that emulated account ID; skipping that lookup while
setting `allowed_account_ids` makes `terraform plan` fail. Never use this
provider configuration with real AWS credentials.

```bash
curl -f http://localhost:4566/_localstack/health
terraform -chdir=infrastructure/terraform/localstack init
terraform -chdir=infrastructure/terraform/localstack fmt -check
terraform -chdir=infrastructure/terraform/localstack validate
terraform -chdir=infrastructure/terraform/localstack plan -out=phase1.tfplan
terraform -chdir=infrastructure/terraform/localstack show phase1.tfplan
```

The reviewed plan should show exactly **three additions**, with no changes or
destructions, provided these resources are not already managed in state.
Do not apply until that plan has been reviewed. Phase 1 acceptance also
requires a successful apply and read checks for the S3 bucket, ECR repository,
and secret. The secret resource has no stored API key. Phase 2 can then add
the router image and ECS task separately.

## Infrastructure tests

The tests use Terraform's mocked AWS provider and do not create cloud
resources:

```bash
sh tests/infrastructure/test_terraform.sh
```
