output "instance_name"       { value = google_sql_database_instance.main.name }
output "connection_name"     { value = google_sql_database_instance.main.connection_name }
output "private_ip_address"  { value = google_sql_database_instance.main.private_ip_address }
output "database_name"       { value = google_sql_database.main.name }
output "database_user"       { value = google_sql_user.app.name }
output "database_url" {
  value     = "postgresql://${google_sql_user.app.name}:${google_sql_user.app.password}@${google_sql_database_instance.main.private_ip_address}:5432/${google_sql_database.main.name}"
  sensitive = true
}
