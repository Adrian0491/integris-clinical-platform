terraform {
  backend "gcs" {
    bucket = "YOUR_GCP_PROJECT_ID-tfstate"
    prefix = "integris/prod"
  }
}
