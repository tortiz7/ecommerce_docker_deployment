output "backend_sg_id" {
    value = aws_security_group.backend_sg.id
}

output "frontend_server_ids" {
  value = [for instance in aws_instance.frontend_server : instance.id]
}

output "backend_server_ids" {
  value = [for instance in aws_instance.backend_server : instance.id]
}