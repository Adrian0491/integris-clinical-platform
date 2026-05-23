output "host"       { value = google_redis_instance.main.host }
output "port"       { value = google_redis_instance.main.port }
output "auth_string" {
  value     = google_redis_instance.main.auth_string
  sensitive = true
}
output "redis_url" {
  # rediss:// uses TLS; the auth string is passed as the password
  value     = "rediss://:${google_redis_instance.main.auth_string}@${google_redis_instance.main.host}:${google_redis_instance.main.port}/0"
  sensitive = true
}
