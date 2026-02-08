# deploy/terraform/main.tf
terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.0"
    }
  }
}

provider "oci" {
  region = var.region
}

locals {
  is_flex = can(regex("Flex$", var.instance_shape))
  arch    = can(regex("A1", var.instance_shape)) ? "arm64" : "amd64"
}

# Get availability domain
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

# Get image for selected shape
data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

# Compute instance
resource "oci_core_instance" "sentinel" {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[var.availability_domain_index].name
  compartment_id      = var.compartment_ocid
  display_name        = "wan-router-sentinel"
  shape               = var.instance_shape

  dynamic "shape_config" {
    for_each = local.is_flex ? [1] : []
    content {
      ocpus         = var.instance_ocpus
      memory_in_gbs = var.instance_memory_gb
    }
  }

  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.ubuntu.images[0].id
  }

  create_vnic_details {
    subnet_id        = var.subnet_ocid
    assign_public_ip = true
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data          = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
      arch = local.arch
    }))
  }

  freeform_tags = {
    project = "wan-router-notifications"
  }
}
