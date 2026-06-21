variable "atlas_org_id" {
  type        = string
  description = "MongoDB Atlas organization ID that will own the project."
}

variable "project_name" {
  type        = string
  description = "MongoDB Atlas project name to create for this deal-intel environment."
  default     = "deal-intel-dev"
}

variable "environment" {
  type        = string
  description = "Short environment label used for naming and project tags."
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.environment))
    error_message = "environment must be 2-31 lowercase letters, numbers, or hyphens, starting with a letter."
  }
}

variable "cluster_name" {
  type        = string
  description = "Atlas cluster name. Renaming a cluster recreates it."
  default     = "deal-intel-dev"
}

variable "cluster_provider_name" {
  type        = string
  description = "Atlas cluster provider. TENANT keeps the default M0 cost-safe path; FLEX or AWS/GCP/AZURE are explicit upgrades."
  default     = "TENANT"

  validation {
    condition     = contains(["TENANT", "FLEX", "AWS", "GCP", "AZURE"], upper(var.cluster_provider_name))
    error_message = "cluster_provider_name must be one of TENANT, FLEX, AWS, GCP, or AZURE."
  }
}

variable "backing_provider_name" {
  type        = string
  description = "Backing cloud for TENANT or FLEX clusters."
  default     = "AWS"

  validation {
    condition     = contains(["AWS", "GCP", "AZURE"], upper(var.backing_provider_name))
    error_message = "backing_provider_name must be one of AWS, GCP, or AZURE."
  }
}

variable "cluster_region_name" {
  type        = string
  description = "Atlas region name such as US_EAST_1. Use Atlas region names, not raw cloud region IDs."
  default     = "US_EAST_1"
}

variable "cluster_instance_size" {
  type        = string
  description = "Atlas instance size. The default M0 is valid only for TENANT clusters; use M10+ for dedicated pro paths."
  default     = "M0"
}

variable "dedicated_electable_nodes" {
  type        = number
  description = "Electable node count for dedicated AWS/GCP/AZURE clusters."
  default     = 3

  validation {
    condition     = contains([3, 5, 7], var.dedicated_electable_nodes)
    error_message = "dedicated_electable_nodes must be 3, 5, or 7."
  }
}

variable "enable_backup" {
  type        = bool
  description = "Enable Atlas backups. Keep false for the default M0 PoC; enable explicitly for Flex or dedicated environments."
  default     = false
}

variable "enable_termination_protection" {
  type        = bool
  description = "Enable Atlas termination protection for the cluster."
  default     = true
}

variable "database_name" {
  type        = string
  description = "Application database name for the deal-intel MCP server."
  default     = "deal_intel"
}

variable "database_username" {
  type        = string
  description = "Application database username."
  default     = "deal_intel_app"
}

variable "database_password" {
  type        = string
  description = "Application database password. Prefer TF_VAR_database_password from the shell, not .tfvars."
  sensitive   = true

  validation {
    condition     = length(var.database_password) >= 16
    error_message = "database_password must be at least 16 characters."
  }
}

variable "database_role_name" {
  type        = string
  description = "Built-in Atlas database role for the application user."
  default     = "readWrite"

  validation {
    condition     = contains(["read", "readWrite"], var.database_role_name)
    error_message = "database_role_name must be read or readWrite for this PoC template."
  }
}

variable "ip_access_cidr_blocks" {
  type        = map(string)
  description = "Map of label to CIDR blocks allowed to reach the Atlas project. Use /32 for a single workstation IP."
  default     = {}
}

variable "allow_broad_ip_access" {
  type        = bool
  description = "Set true only for a short-lived PoC if you intentionally need 0.0.0.0/0."
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Additional Atlas project tags."
  default     = {}
}
