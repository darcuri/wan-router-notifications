# deploy/terraform/outputs.tf
output "instance_public_ip" {
  description = "Public IP of the sentinel instance"
  value       = oci_core_instance.sentinel.public_ip
}

output "instance_private_ip" {
  description = "Private IP of the sentinel instance"
  value       = oci_core_instance.sentinel.private_ip
}

output "instance_id" {
  description = "OCID of the instance"
  value       = oci_core_instance.sentinel.id
}

output "instance_shape" {
  description = "Compute shape used for the instance"
  value       = oci_core_instance.sentinel.shape
}

output "instance_region" {
  description = "OCI region where the instance was deployed"
  value       = var.region
}
