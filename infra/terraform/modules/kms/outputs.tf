output "key_ring_id"          { value = google_kms_key_ring.main.id }
output "sql_key_id"           { value = google_kms_crypto_key.sql.id }
output "sql_key_name"         { value = google_kms_crypto_key.sql.name }
output "storage_key_id"       { value = google_kms_crypto_key.storage.id }
output "secrets_key_id"       { value = google_kms_crypto_key.secrets.id }
