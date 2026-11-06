#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)

for environment in aws localstack; do
  terraform_root="$repo_root/infrastructure/terraform/$environment"
  terraform -chdir="$terraform_root" fmt -check -recursive
  terraform -chdir="$terraform_root" init -backend=false -input=false -lockfile=readonly
  terraform -chdir="$terraform_root" validate
  terraform -chdir="$terraform_root" test
done
