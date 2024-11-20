resource "aws_vpc" "main" {
  cidr_block       = "10.0.0.0/16"
  instance_tenancy = "default"

  tags = {
    Name = "wl6vpc"
  }
}

resource "aws_subnet" "public" {
  count = 2
  vpc_id     = aws_vpc.main.id
  cidr_block = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone = element(["us-east-1a", "us-east-1b"], count.index)
  map_public_ip_on_launch = true

  tags = {
    Name = "Public-${count.index +1}"
  }
}

resource "aws_subnet" "private" {
  count = 2
  vpc_id     = aws_vpc.main.id
  cidr_block = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 2)
  availability_zone = element(["us-east-1a", "us-east-1b"], count.index)
  map_public_ip_on_launch = false

  tags = {
    Name = "Private-${count.index +1}"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "IGW"
  }
}

resource "aws_eip" "nat_ip" {
  domain = "vpc"
}

resource "aws_nat_gateway" "nat_gw" {
  allocation_id = aws_eip.nat_ip.id
  subnet_id     = aws_subnet.public[0].id 

  tags = {
    Name = "NAT-Gateway"
  }
}


resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "Public_Route_Table"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat_gw.id
  }

  tags = {
    Name = "Private_Route_Table"
  }
}

resource "aws_route_table_association" "igw_assn" {
 count = length(aws_subnet.public)  
 subnet_id = aws_subnet.public[count.index].id  
 route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private_assn" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_vpc_peering_connection" "peer" {
  vpc_id        = aws_vpc.main.id                     
  peer_vpc_id   = "vpc-04776a218231f7c14"             
  auto_accept   = true                                

  tags = {
    Name = "WL6-Default-VPC-Peer"
  }
}

resource "aws_route" "public_peer_route" {
  count                  = length(aws_subnet.public)
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "172.31.0.0/16"            
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}

resource "aws_route" "private_peer_route" {
  count                  = length(aws_subnet.private)
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "172.31.0.0/16"            
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}

resource "aws_route" "default_peer_route" {
  route_table_id         = "rtb-0adb5c3fb76733aae"             
  destination_cidr_block = aws_vpc.main.cidr_block    
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}