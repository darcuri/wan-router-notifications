# deploy/terraform/variables.tf
variable "region" {
  description = "OCI region"
  type        = string
  default     = "us-ashburn-1"
}

variable "compartment_ocid" {
  description = "OCID of the compartment"
  type        = string
}

variable "subnet_ocid" {
  description = "OCID of the subnet"
  type        = string
}

variable "ssh_public_key" {
  description = "Public SSH key for instance access"
  type        = string
}

variable "instance_shape" {
  description = "Compute shape (VM.Standard.A1.Flex for ARM, VM.Standard.E2.1.Micro for x86)"
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  description = "Number of OCPUs (1-4 for free tier ARM)"
  type        = number
  default     = 1
}

variable "instance_memory_gb" {
  description = "Memory in GB (up to 6GB per OCPU for free tier)"
  type        = number
  default     = 6
}

variable "availability_domain_index" {
  description = "Index of the availability domain to use (try 0, 1, or 2 if capacity is unavailable)"
  type        = number
  default     = 0
}
