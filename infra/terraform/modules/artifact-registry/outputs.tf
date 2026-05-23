output "repository_id"   { value = google_artifact_registry_repository.images.repository_id }
output "repository_name" { value = google_artifact_registry_repository.images.name }
output "registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
