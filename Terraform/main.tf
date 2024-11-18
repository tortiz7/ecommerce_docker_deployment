# Configure the AWS provider block. This tells Terraform which cloud provider to use and 
# how to authenticate (access key, secret key, and region) when provisioning resources.
# Note: Hardcoding credentials is not recommended for production use. Instead, use environment variables
# or IAM roles to manage credentials securely.
provider "aws" {
  access_key = var.aws_access_key          # Replace with your AWS access key ID (leave empty if using IAM roles or env vars)
  secret_key = var.aws_secret_key          # Replace with your AWS secret access key (leave empty if using IAM roles or env vars)
  region     = var.region              # Specify the AWS region where resources will be created (e.g., us-east-1, us-west-2)
}


module "VPC"{
  source = "./VPC"
} 

module "EC2"{
  source = "./EC2"
  vpc_id = module.VPC.vpc_id
  public_subnet = module.VPC.public_subnet
  private_subnet = module.VPC.private_subnet
  instance_type = var.instance_type
  region = var.region
  frontend_count = var.frontend_count
  backend_count = var.backend_count
  db_name = var.db_name
  db_username = var.db_username
  db_password = var.db_password
  rds_address = module.RDS.rds_address
  rds_endpoint = module.RDS.rds_endpoint
  postgres_db = module.RDS.postgres_db
  rds_sg_id = module.RDS.rds_sg_id
  alb_sg_id = module.ALB.alb_sg_id
  frontend_port = var.frontend_port
  dockerhub_user = var.dockerhub_user
  dockerhub_pass = var.dockerhub_pass
  nat_gw = module.VPC.nat_gw

}

module "RDS"{
  source = "./RDS"
  db_instance_class = var.db_instance_class
  db_name           = var.db_name
  db_username       = var.db_username
  db_password       = var.db_password
  vpc_id            = module.VPC.vpc_id
  private_subnet    = module.VPC.private_subnet
  backend_sg_id     = module.EC2.backend_sg_id

  
}

module "ALB"{
  source = "./ALB"
  alb_name = var.alb_name
  backend_port = var.backend_port
  frontend_port = var.frontend_port
  backend_count = var.backend_count
  frontend_count = var.frontend_count
  frontend_server_ids = module.EC2.frontend_server_ids
  backend_server_ids = module.EC2.backend_server_ids
  public_subnet = module.VPC.public_subnet
  vpc_id = module.VPC.vpc_id

}