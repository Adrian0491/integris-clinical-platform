output "lb_ip_address"    { value = google_compute_global_address.lb_ip.address }
output "ssl_cert_name"    { value = google_compute_managed_ssl_certificate.cert.name }
output "backend_service_id" { value = google_compute_backend_service.api.id }
