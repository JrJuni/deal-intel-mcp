# MongoDB Atlas Terraform PoC

This directory contains a small Terraform template for creating a MongoDB Atlas
project that can back the `full` profile, with explicit upgrade knobs for later
`pro` infrastructure experiments.

Defaults are intentionally cost-safe:

- Atlas project
- M0 tenant cluster on AWS `US_EAST_1`
- application database user
- optional IP access list entries
- sensitive SRV connection string output

Terraform owns infrastructure only. Deal records, sample data, schema
application, chart-ready refreshes, product-context indexing, and Atlas Vector
Search index creation stay in the app and CLI.

## Prerequisites

- Terraform installed locally.
- MongoDB Atlas organization ID.
- MongoDB Atlas Service Account credentials with permission to create projects,
  clusters, database users, and access list entries.

The MongoDB Atlas Terraform provider recommends Service Account authentication.
Set credentials in the shell rather than in `.tfvars` files:

```powershell
$env:MONGODB_ATLAS_CLIENT_ID = "replace-with-atlas-service-account-client-id"
$env:MONGODB_ATLAS_CLIENT_SECRET = "replace-with-atlas-service-account-client-secret"
$env:TF_VAR_atlas_org_id = "replace-with-atlas-org-id"
$env:TF_VAR_database_password = "replace-with-strong-db-password"
```

Optionally restrict Atlas access to your current workstation IP:

```powershell
$env:TF_VAR_ip_access_cidr_blocks = '{"workstation":"203.0.113.10/32"}'
```

## Validate

Run from this directory:

```powershell
terraform fmt -check
terraform init -backend=false
terraform validate
```

If you downloaded the Windows zip instead of installing Terraform into `PATH`,
point PowerShell at the extracted binary:

```powershell
$terraform = "C:\path\to\terraform.exe"
& $terraform version
& $terraform fmt -check
& $terraform init -backend=false
& $terraform validate
```

`terraform init` downloads the MongoDB Atlas provider and may create
`.terraform.lock.hcl`. The `.terraform/` plugin directory is ignored.

## Plan And Apply

Review the plan before applying:

```powershell
terraform plan
terraform apply
```

After apply, read the sensitive SRV host only when needed:

```powershell
terraform output -raw standard_srv_connection_string
```

Build the app `MONGODB_URI` outside Terraform output logs:

```powershell
$srv_host = (terraform output -raw standard_srv_connection_string) -replace "^mongodb\\+srv://", ""
$env:MONGODB_URI = "mongodb+srv://deal_intel_app:<password>@$srv_host/deal_intel?retryWrites=true&w=majority"
```

Replace `<password>` with the same password provided through
`TF_VAR_database_password`, then store the URI in your local shell or secret
manager.

## Upgrade Knobs

Use the default `TENANT` + `M0` path for disposable dev projects.

For Flex, set:

```powershell
$env:TF_VAR_cluster_provider_name = "FLEX"
```

For a paid dedicated/pro cluster, set an explicit provider and M10+ tier:

```powershell
$env:TF_VAR_cluster_provider_name = "AWS"
$env:TF_VAR_cluster_instance_size = "M10"
$env:TF_VAR_enable_backup = "true"
```

Keep paid search/vector-search infrastructure behind explicit follow-up changes.
This PoC only creates the cluster prerequisite; app-level indexing remains a
deal-intel CLI/app responsibility.

## Safety Notes

- Do not commit `.tfvars`, local state, Atlas API keys, database passwords, or
  generated connection strings.
- Terraform state can contain sensitive values, including database user
  passwords. Keep real environments in encrypted remote state.
- Start with a new dev project and cluster before importing or managing an
  existing Atlas environment.
- `0.0.0.0/0` is blocked unless `allow_broad_ip_access=true`; use it only for a
  short-lived PoC.
- Termination protection is enabled by default. Disable it intentionally before
  destroying a disposable cluster.
- Do not use this PoC as-is for production deal data without a separate review
  of state storage, access control, backups, deletion policy, and network access.
