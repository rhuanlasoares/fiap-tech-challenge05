resource "google_secret_manager_secret" "aws_access_key_id" {
  project   = var.project_id
  secret_id = var.aws_access_key_id["secret_id"]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  deletion_protection = false
}

resource "google_secret_manager_secret_version" "aws_access_key_id_version" {
  secret      = google_secret_manager_secret.aws_access_key_id.id
  secret_data = var.aws_access_key_id["secret_data"]
}

resource "google_secret_manager_secret" "aws_secret_access_key" {
  project   = var.project_id
  secret_id = var.aws_secret_access_key["secret_id"]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  deletion_protection = false
}

resource "google_secret_manager_secret_version" "aws_secret_access_key_version" {
  secret      = google_secret_manager_secret.aws_secret_access_key.id
  secret_data = var.aws_secret_access_key["secret_data"]
}

resource "google_secret_manager_secret" "aws_session_token" {
  project   = var.project_id
  secret_id = var.aws_session_token["secret_id"]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  deletion_protection = false
}

resource "google_secret_manager_secret_version" "aws_session_token_version" {
  secret      = google_secret_manager_secret.aws_session_token.id
  secret_data = var.aws_session_token["secret_data"]
}

resource "google_secret_manager_secret" "ngo_password" {
  project   = var.project_id
  secret_id = var.ngo_secret["secret_id"]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  deletion_protection = false
}

resource "google_secret_manager_secret_version" "ngo_password_version" {
  secret      = google_secret_manager_secret.ngo_password.id
  secret_data = var.ngo_secret["secret_data"]
}

resource "google_secret_manager_secret" "donation_password" {
  project   = var.project_id
  secret_id = var.donation_secret["secret_id"]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  deletion_protection = false
}

resource "google_secret_manager_secret_version" "donation_password_version" {
  secret      = google_secret_manager_secret.donation_password.id
  secret_data = var.donation_secret["secret_data"]
}

resource "google_secret_manager_secret" "sm_sqs_queue_url" {
  project   = var.project_id
  secret_id = var.sm_sqs_queue_url["secret_id"]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  deletion_protection = false
}


resource "google_secret_manager_secret_version" "sm_sqs_queue_url_version" {
  secret      = google_secret_manager_secret.sm_sqs_queue_url.id
  secret_data = var.sm_sqs_queue_url["secret_data"]
}
resource "google_secret_manager_secret" "new_relic_api_key" {
  project   = var.project_id
  secret_id = var.new_relic_api_key["secret_id"]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  deletion_protection = false
}

resource "google_secret_manager_secret_version" "new_relic_api_key_version" {
  secret      = google_secret_manager_secret.new_relic_api_key.id
  secret_data = var.new_relic_api_key["secret_data"]
}


resource "google_secret_manager_secret" "gemini_api_key" {
  project   = var.project_id
  secret_id = var.gemini_api_key["secret_id"]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  deletion_protection = false
}

resource "google_secret_manager_secret_version" "gemini_api_key_version" {
  secret      = google_secret_manager_secret.gemini_api_key.id
  secret_data = var.gemini_api_key["secret_data"]
}

resource "google_secret_manager_secret" "webhook_slack" {
  project   = var.project_id
  secret_id = var.webhook_slack["secret_id"]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  deletion_protection = false
}

resource "google_secret_manager_secret_version" "webhook_slack_version" {
  secret      = google_secret_manager_secret.webhook_slack.id
  secret_data = var.webhook_slack["secret_data"]
}