output "sa_email" {
  description = "Email addresses of the created Service Accounts."
  value = {
    for sa_name, sa in google_service_account.service_accounts :
    sa_name => sa.email
  }
}

output "sa_member" {
  description = "Member identifiers of the created Service Accounts."
  value = {
    for sa_name, sa in google_service_account.service_accounts :
    sa_name => sa.member
  }
}

output "sa_name" {
  description = "Member identifiers of the created Service Accounts."
  value = {
    for sa_name, sa in google_service_account.service_accounts :
    sa_name => sa.name
  }
}
