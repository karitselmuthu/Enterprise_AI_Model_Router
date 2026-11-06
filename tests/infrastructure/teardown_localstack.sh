#!/bin/sh
set -eu

if [ "${1:-}" != "--yes" ]; then
  echo "Usage: LOCALSTACK_ENDPOINT=http://localhost:4567 TERRAFORM_ROOT=/path/to/localstack/root $0 --yes" >&2
  exit 2
fi

endpoint=${LOCALSTACK_ENDPOINT:-}
root=${TERRAFORM_ROOT:-}
case "$endpoint" in
  http://localhost:[0-9]*|http://127.0.0.1:[0-9]*) ;;
  *) echo "Refusing non-local endpoint" >&2; exit 2 ;;
esac
if [ -z "$root" ] || [ ! -f "$root/terraform.tfstate" ] || [ ! -f "$root/providers.tf" ]; then
  echo "Provide a Terraform root with an existing local state file" >&2
  exit 2
fi

terraform -chdir="$root" destroy -var="localstack_endpoint=$endpoint" -auto-approve
