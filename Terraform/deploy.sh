#!/bin/bash

# Update & upgrade packages on the EC2s
sudo apt update
sudo apt upgrade -y

# Put key in authorized_keys folder

echo "${pub_key}" >> /home/ubuntu/.ssh/authorized_keys

# Download Node Exporter
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.0/node_exporter-1.6.0.linux-amd64.tar.gz
tar xvfz node_exporter-1.6.0.linux-amd64.tar.gz
sudo mv node_exporter-1.6.0.linux-amd64/node_exporter /usr/local/bin/
rm -rf node_exporter-1.6.0.linux-amd64*

# Create a service file for Node Exporter
cat <<EOL | sudo tee /etc/systemd/system/node_exporter.service
[Unit]
Description=Node Exporter

[Service]
User=ubuntu
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOL

# Start and enable Node Exporter
sudo systemctl daemon-reload
sudo systemctl start node_exporter
sudo systemctl enable node_exporter

sudo systemctl status node_exporter || { echo "Node Exporter failed to start"; exit 1; }

# Install Docker:
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sleep 60

### Post Install Docker Group
sudo groupadd docker
sudo usermod -aG docker ubuntu
sudo usermod -aG docker jenkins
newgrp docker

# Verify Docker Compose:

docker compose --version || { echo "docker compose not found"; exit 1; }

docker_pass=${docker_pass}
docker_user=${docker_user}

# Log into DockerHub with the credential variables
echo "$docker_pass" | docker login --username "$docker_user" --password-stdin

# Create docker-compose.yaml

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Creating app directory..."
mkdir -p /app
cd /app
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Created and moved to /app"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Creating docker-compose.yml..."
cat > docker-compose.yml <<EOF
${docker_compose}
EOF
echo "[$(date '+%Y-%m-%d %H:%M:%S')] docker-compose.yml created"

docker compose pull

docker compose up -d --force-recreate
echo "Docker Compose services deployed."

cat docker-compose.yml

# Clean up Docker and Logout

docker system prune -f
docker logout