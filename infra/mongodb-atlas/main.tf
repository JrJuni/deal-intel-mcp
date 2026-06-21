locals {
  cluster_provider_name = upper(var.cluster_provider_name)
  backing_provider_name = upper(var.backing_provider_name)
  cluster_instance_size = upper(var.cluster_instance_size)
  cluster_region_name   = upper(var.cluster_region_name)

  is_flex_cluster      = local.cluster_provider_name == "FLEX"
  is_tenant_cluster    = local.cluster_provider_name == "TENANT"
  is_dedicated_cluster = !local.is_tenant_cluster && !local.is_flex_cluster

  project_tags = merge(
    {
      ManagedBy   = "Terraform"
      Application = "deal-intel-mcp"
      Environment = var.environment
    },
    var.tags
  )

  standard_srv_connection_string = one(concat(
    mongodbatlas_advanced_cluster.tenant[*].connection_strings.standard_srv,
    mongodbatlas_advanced_cluster.flex[*].connection_strings.standard_srv,
    mongodbatlas_advanced_cluster.dedicated[*].connection_strings.standard_srv
  ))
}

resource "mongodbatlas_project" "this" {
  name   = var.project_name
  org_id = var.atlas_org_id
  tags   = local.project_tags
}

resource "mongodbatlas_advanced_cluster" "tenant" {
  count = local.is_tenant_cluster ? 1 : 0

  project_id = mongodbatlas_project.this.id
  name       = var.cluster_name

  cluster_type                   = "REPLICASET"
  backup_enabled                 = false
  termination_protection_enabled = var.enable_termination_protection

  replication_specs = [
    {
      region_configs = [
        {
          provider_name         = "TENANT"
          backing_provider_name = local.backing_provider_name
          region_name           = local.cluster_region_name
          priority              = 7
          electable_specs = {
            instance_size = "M0"
          }
        }
      ]
    }
  ]

  lifecycle {
    precondition {
      condition     = !local.is_tenant_cluster || local.cluster_instance_size == "M0"
      error_message = "TENANT clusters must use cluster_instance_size M0. Use FLEX or a dedicated provider for paid tiers."
    }

    precondition {
      condition     = !var.enable_backup || !local.is_tenant_cluster
      error_message = "enable_backup must stay false for the default TENANT/M0 PoC path."
    }
  }
}

resource "mongodbatlas_advanced_cluster" "flex" {
  count = local.is_flex_cluster ? 1 : 0

  project_id = mongodbatlas_project.this.id
  name       = var.cluster_name

  cluster_type                   = "REPLICASET"
  backup_enabled                 = var.enable_backup
  termination_protection_enabled = var.enable_termination_protection

  replication_specs = [
    {
      region_configs = [
        {
          provider_name         = "FLEX"
          backing_provider_name = local.backing_provider_name
          region_name           = local.cluster_region_name
          priority              = 7
        }
      ]
    }
  ]
}

resource "mongodbatlas_advanced_cluster" "dedicated" {
  count = local.is_dedicated_cluster ? 1 : 0

  project_id = mongodbatlas_project.this.id
  name       = var.cluster_name

  cluster_type                   = "REPLICASET"
  backup_enabled                 = var.enable_backup
  termination_protection_enabled = var.enable_termination_protection

  replication_specs = [
    {
      region_configs = [
        {
          provider_name = local.cluster_provider_name
          region_name   = local.cluster_region_name
          priority      = 7
          electable_specs = {
            instance_size = local.cluster_instance_size
            node_count    = var.dedicated_electable_nodes
          }
        }
      ]
    }
  ]

  lifecycle {
    precondition {
      condition     = !contains(["M0", "M2", "M5"], local.cluster_instance_size)
      error_message = "Dedicated providers AWS/GCP/AZURE require an explicit M10+ cluster_instance_size."
    }
  }
}

resource "mongodbatlas_database_user" "app" {
  depends_on = [
    mongodbatlas_advanced_cluster.tenant,
    mongodbatlas_advanced_cluster.flex,
    mongodbatlas_advanced_cluster.dedicated,
  ]

  username           = var.database_username
  password           = var.database_password
  project_id         = mongodbatlas_project.this.id
  auth_database_name = "admin"

  roles {
    role_name     = var.database_role_name
    database_name = var.database_name
  }

  scopes {
    name = var.cluster_name
    type = "CLUSTER"
  }
}

resource "mongodbatlas_project_ip_access_list" "cidr_blocks" {
  for_each = var.ip_access_cidr_blocks

  project_id = mongodbatlas_project.this.id
  cidr_block = each.value
  comment    = "deal-intel-mcp ${var.environment}: ${each.key}"

  lifecycle {
    precondition {
      condition     = var.allow_broad_ip_access || each.value != "0.0.0.0/0"
      error_message = "0.0.0.0/0 is blocked by default. Set allow_broad_ip_access=true only for a short-lived PoC."
    }
  }
}
