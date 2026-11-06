# Terraform environments

These are **separate Terraform root configurations and state files**:

- `aws/` provisions a private ECS Fargate router, ECR, VPC networking, an
  internal ALB, CloudWatch logs, and an ECS execution role.
- `localstack/` provisions the Phase 1 bucket, ECR repository, and test secret,
  plus the Phase 2 ECS service and Phase 3 VPC, IAM, secret injection, and ALB.

The AWS configuration has not been applied. Review its `terraform plan` before
any `apply`; AWS NAT Gateway and ALB resources incur charges even when
`deploy_service = false`. Use a remote, encrypted state backend for team use;
the starter files use local state, which is ignored by Git. Do not place real
API keys in `.tfvars` or commit state files.

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
token, and a LocalStack plan that includes ECR and ECS. LocalStack must have
access to `/var/run/docker.sock` to start ECS tasks. The provider points the
resource services at `http://localhost:4566` by default, uses dummy credentials,
and restricts the account ID to `000000000000`. STS is mapped locally so the
provider can read that emulated account ID. S3 Control is mapped locally
because the AWS provider uses it to read bucket tags. Never use this provider
configuration with real AWS credentials.

```bash
curl -f http://localhost:4566/_localstack/health
terraform -chdir=infrastructure/terraform/localstack init
terraform -chdir=infrastructure/terraform/localstack fmt -check
terraform -chdir=infrastructure/terraform/localstack validate
terraform -chdir=infrastructure/terraform/localstack plan -out=phase1.tfplan
terraform -chdir=infrastructure/terraform/localstack show phase1.tfplan
terraform -chdir=infrastructure/terraform/localstack apply phase1.tfplan
```

For a fresh instance, first create the bucket, repository and secret, build and
push the image, then apply the ECS resources. The initial bootstrap plan has
four additions. Review each plan before applying. The secret version
stores only `OPENAI_API_KEY=localstack-test-only`; this value cannot authenticate
to a real model provider, and Terraform keeps it in local state. After applying,
check the three service resources and run `terraform plan` again to confirm no
drift.

Build and push the router image before deploying the ECS service. Use a tag
unique to each build and pass it as `image_tag`. For a LocalStack instance on
another local port, pass `-var='localstack_endpoint=http://localhost:4567'`
on every Terraform plan or apply and keep a separate Terraform state file.

```bash
LOCAL_REPO_URL=$(terraform -chdir=infrastructure/terraform/localstack output -raw ecr_repository_url)
LOCAL_TAG=build-001
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:4566 ecr get-login-password \
  | docker login --username AWS --password-stdin "${LOCAL_REPO_URL%%/*}"
docker build -t "$LOCAL_REPO_URL:$LOCAL_TAG" .
docker push "$LOCAL_REPO_URL:$LOCAL_TAG"
terraform -chdir=infrastructure/terraform/localstack plan \
  -var="image_tag=$LOCAL_TAG" -out=phase2.tfplan
terraform -chdir=infrastructure/terraform/localstack apply phase2.tfplan
```

The ECS service now uses dedicated local VPC subnets and security groups. It
injects a deliberately fake `OPENAI_API_KEY` from Secrets Manager and attaches
an execution role. The internal ALB exposes `/health/ready` through LocalStack.
For a secondary emulator on port 4567, the smoke URL is
`http://enterprise-ai-router-local.elb.localhost.localstack.cloud:4567/health/ready`.
LocalStack's default IAM enforcement is disabled, and its container networking
does not prove real AWS subnet isolation or provider API egress. The separate
`aws/` configuration includes the NAT path needed for real private tasks.

On 2026-11-07, the LocalStack apply completed on this workstation. S3, ECR,
and the fake credential were read back successfully; a subsequent plan found
no changes. This LocalStack instance reported persistence disabled, so those
resources may disappear if the emulator restarts while local Terraform state
remains. Reconcile state against a fresh instance before applying again.

Phase 2 was also applied to an isolated LocalStack instance on port 4567 with
Docker socket access. Its ECS task started healthy. The original port-4566
instance lacks that mount; its cluster and task definition were created but
service creation failed with `Docker not available`. Its state is preserved.

## Infrastructure tests

The tests use Terraform's mocked AWS provider and do not create cloud
resources:

```bash
sh tests/infrastructure/test_terraform.sh
```
