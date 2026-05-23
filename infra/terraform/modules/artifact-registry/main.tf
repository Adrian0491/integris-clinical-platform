# =============================================================================
# Artifact Registry — Docker repository for container images
# =============================================================================

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "${var.app_name}-images"
  format        = "DOCKER"
  description   = "Integris Clinical Platform container images"

  labels = var.labels

  cleanup_policies {
    id     = "keep-recent-releases"
    action = "KEEP"
    most_recent_versions {
      # Keep the 10 most-recent tagged images; delete untagged after 14 days
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state    = "UNTAGGED"
      older_than   = "1209600s"   # 14 days
    }
  }
}
