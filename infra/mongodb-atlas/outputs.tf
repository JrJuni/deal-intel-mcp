output "atlas_project_id" {
  description = "Atlas project ID created by this template."
  value       = mongodbatlas_project.this.id
}

output "atlas_project_name" {
  description = "Atlas project name created by this template."
  value       = mongodbatlas_project.this.name
}

output "cluster_name" {
  description = "Atlas cluster name."
  value       = var.cluster_name
}

output "standard_srv_connection_string" {
  description = "SRV connection string host for the cluster. Add username, password, and database name outside Terraform output logs."
  value       = local.standard_srv_connection_string
  sensitive   = true
}

output "database_name" {
  description = "Database name configured for the deal-intel app user."
  value       = var.database_name
}

output "database_username" {
  description = "Database username configured for the deal-intel app user."
  value       = mongodbatlas_database_user.app.username
}
