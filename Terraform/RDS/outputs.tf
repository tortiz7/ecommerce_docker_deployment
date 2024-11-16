output "rds_address" {
  value = aws_db_instance.postgres_db.address
}

output "rds_endpoint"{
  value = aws_db_instance.postgres_db.endpoint
}

output "rds_sg_id" {
    value = aws_security_group.rds_sg.id
}

output "postgres_db"{
  value = aws_db_instance.postgres_db.id
}