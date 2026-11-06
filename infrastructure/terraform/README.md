# Terraform environments

These are **separate Terraform root configurations and state files**:

- `aws/` provisions a private ECS Fargate router, ECR, VPC networking, an
  internal ALB, CloudWatch logs, and an ECS execution role.
- `localstack/` provisions local S3, ECR, Secrets Manager, VPC metadata, logs,
  and an ECS task/service against a LocalStack Desktop instance. Its Fargate
  task runs on the local Docker engine; it does **not** recreate AWS networking
  or API Gateway behavior.

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
token, and a LocalStack plan that includes ECR. The provider points at
`http://localhost:4566` with local test credentials. It must not be used for
real AWS.

```bash
terraform -chdir=infrastructure/terraform/localstack init
terraform -chdir=infrastructure/terraform/localstack plan
terraform -chdir=infrastructure/terraform/localstack apply
```

This first apply leaves the local ECS service disabled. Push a uniquely tagged
image to the repository URL from `terraform output -raw ecr_repository_url`,
then enable the service:

```bash
LOCAL_REPO_URL=$(terraform -chdir=infrastructure/terraform/localstack output -raw ecr_repository_url)
LOCAL_TAG=build-001
docker build -t "$LOCAL_REPO_URL:$LOCAL_TAG" .
docker push "$LOCAL_REPO_URL:$LOCAL_TAG"
terraform -chdir=infrastructure/terraform/localstack apply \
  -var='deploy_service=true' -var="image_tag=$LOCAL_TAG"
```

LocalStack's ECS executor uses Docker on the desktop, so inspect the spawned
container or its ECS task description to find the locally mapped port. For a
simpler application smoke test, use `docker compose up --build`. Repeat
networking, IAM, secret injection, authenticated access, and live-provider
tests on AWS before production use.

## Infrastructure tests

The tests use Terraform's mocked AWS provider and do not create cloud
resources:

```bash
sh tests/infrastructure/test_terraform.sh
```
