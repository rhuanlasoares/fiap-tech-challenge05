module "aws" {
  source = "./modules/aws"
}

locals {
  sqs_queue_url = {
    secret_id   = "sm-sqs-queue-url"
    secret_data = module.aws.sqs_queue_url
  }
}

module "apis" {
  source = "./modules/apis"

  project_id         = var.project_id
  services_apis_list = var.services_apis_list
}

module "cloud_storage" {
  source = "./modules/bucket"

  project_id  = var.project_id
  region      = var.region
  bucket_name = var.bucket_name
  labels_bucket = var.labels_bucket
}

module "wifederation" {
  depends_on = [module.apis]
  source     = "./modules/wifederation"

  project_id                         = var.project_id
  workload_identity_pool_id          = var.workload_identity_pool_id
  display_name_wip                   = var.display_name_wip
  workload_identity_pool_provider_id = var.workload_identity_pool_provider_id
  display_name_wip_provider          = var.display_name_wip_provider
  owner_and_repository               = var.owner_and_repository
  sa_wifederation_email              = var.sa_wifederation_email
}

module "artifact_registry" {
  depends_on = [module.apis]
  for_each   = var.artreg

  source      = "./modules/artifact_registry"
  project_id  = var.project_id
  region      = var.region
  name_artreg = each.value.name_artreg
  description = each.value.description
}

module "vpc" {
  depends_on = [module.apis]
  source     = "./modules/vpc"

  project_id               = var.project_id
  vpc_name                 = var.vpc_name
  subnet_name              = var.subnet_name
  region                   = var.region
  router_name              = var.router_name
  nat_name                 = var.nat_name
  ip_cidr_range_subnet_gke = var.ip_cidr_range_subnet_gke
  range_name_pods          = var.range_name_pods
  ip_cidr_range_pods       = var.ip_cidr_range_pods
  range_name_services      = var.range_name_services
  ip_cidr_range_services   = var.ip_cidr_range_services
  psa_name                 = var.psa_name
  sa_gke_email             = module.service_accounts.sa_email["sa-gke-fiap"]
}

module "service_accounts" {
  depends_on = [module.apis]
  source     = "./modules/service_account"

  project_id       = var.project_id
  service_accounts = var.service_accounts
}

module "secret_manager" {
  depends_on = [module.apis]
  source     = "./modules/secret_manager"

  project_id                  = var.project_id
  region                      = var.region
  aws_access_key_id           = var.aws_access_key_id
  aws_secret_access_key       = var.aws_secret_access_key
  aws_session_token           = var.aws_session_token
  ngo_secret                  = var.cloud_sql["ngo-service"].password
  donation_secret             = var.cloud_sql["donation-service"].password
  sm_sqs_queue_url            = local.sqs_queue_url
  new_relic_api_key           = var.new_relic_api_key
}

module "iam" {
  depends_on = [
    module.vpc,
    module.service_accounts,
    module.artifact_registry,
    module.secret_manager
  ]
  source         = "./modules/iam"
  project_id     = var.project_id
  project_number = var.project_number
  region         = var.region
  subnet_name    = var.subnet_name
  sa_gke_member  = module.service_accounts.sa_member["sa-gke-fiap"]
  artreg         = var.artreg
  sa_inside_gke  = var.sa_inside_gke
  sa_gke_name    = module.service_accounts.sa_name["sa-gke-fiap"]
  secrets = {
    aws_access_key_id           = var.aws_access_key_id
    aws_secret_access_key       = var.aws_secret_access_key
    aws_session_token           = var.aws_session_token
    ngo_secret                  = var.cloud_sql["ngo-service"].password
    donation_secret             = var.cloud_sql["donation-service"].password
    sm_sqs_queue_url            = local.sqs_queue_url
    new_relic_api_key           = var.new_relic_api_key
  }
}

# module "compute_engine" {
#   depends_on = [module.apis]

#   source               = "./modules/compute_engine"
#   project_id           = var.project_id
#   region               = var.region
#   network_self_link    = module.vpc.vpc_self_link
#   subnetwork_self_link = module.vpc.subnet_self_link
#   sa_gke_email         = module.service_accounts.sa_email["sa-gke-fiap"]
# }

module "cloud_sql" {
  depends_on = [module.vpc]
  source     = "./modules/cloud_sql"
  for_each   = var.cloud_sql

  project_id               = var.project_id
  region                   = var.region
  vpc_self_link            = module.vpc.vpc_self_link
  database_version         = each.value.database_version
  instance_tier            = each.value.instance_tier
  instance_labels          = each.value.instance_labels
  cloud_sql_instance_name  = each.value.cloud_sql_instance_name
  psa_name                 = var.psa_name
  sa_gke_email             = module.service_accounts.sa_email["sa-gke-fiap"]
  ip_cidr_range_subnet_gke = var.ip_cidr_range_subnet_gke
  database_name            = each.value.database_name
  username                 = each.value.username
  password                 = each.value.password
}

module "gke" {
  depends_on = [module.vpc, module.iam]
  source     = "./modules/gke"

  project_id          = var.project_id
  region              = var.region
  gke_cluster_name    = var.gke_cluster_name
  gke_resource_labels = var.gke_resource_labels
  range_name_pods     = var.range_name_pods
  range_name_services = var.range_name_services
  vpc_self_link       = module.vpc.vpc_self_link
  subnet_self_link    = module.vpc.subnet_self_link
  sa_gke_member       = module.service_accounts.sa_email["sa-gke-fiap"]
}
