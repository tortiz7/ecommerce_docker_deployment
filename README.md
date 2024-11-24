# Containerized Ecommerce Webapp Deployment, featuring IaC, CI/CD and Monitoring

---
### PURPOSE

Hello! If you've been following my Workload series for deploying Flask Applications using AWS infrastructure, then welcome to the sixth entry. The purpose of Workload 6 is to build upon the fault tolerance and expanded availability we created for our Ecommerce application via IaC in Workload 5, this time containzering the appliation code via Docker so we can more easily deploy the application at scale. This Workload emphasizes best practices in cloud deployment, including automating the building of infrastructure with Terraform, containerizing the application code via Docker and managing the building of Docker images via Docker Compose, continuous integration and continuous delivery (CI/CD) with Jenkins, effective resource management across multiple EC2 instances in different subnets and AZ's, and a strong emphasis on monitoring and security. By establishing a clear separation between deployment and production environments, this project aims to enhance system reliability while optimizing resource utilization and operational efficiency.

---
## STEPS

### Create the Jenkins Manager EC2

**Why:** Unlike our previous workloads, this workload will have Jenkins leveraging an agent node to assist in the building, testing and deploying of our Ecommerce application. By separating the managing of Jenkins from the actual deployment of the code, we introduce increased security to our application by siloing credentials and access to one EC2 (our agent EC2, more on that later), while also reducing resource contention that has occurred in the past when one Jenkins workspace was solely responsible for both building the application to test the code logic and provisioning all the infrastructure via Terraform. 

**How:**

1. Navigate to the EC2 services page in AWS and click "Launch Instance".
2. Name the EC2 `Jenkins` and select "Ubuntu" as the OS Image.
3. Select a t3.micro as the instance type.
4. Create a new key pair (and be sure to save the .pem somewhere safe!). 
5. In "Network Settings", choose the default VPC selected for this EC2, with Auto-Assign Public IP enabled.
6. Create a Security Group that allows inbound traffic to the services and applications the EC2 will need and name it after the EC2 it will control.
7. The Inbound rules should allow network traffic on Ports 22 (SSH) and 8080 (Jenkins) and port 8081 (Vscode), and all Outbound traffic.
8. Launch the instance!

Next, we'll connect to the Jenkins server and install Jenkins onto it:

``` bash
#!/bin/bash
sudo apt update -y
sudo apt upgrade -y
sudo apt install -y openjdk-17-jdk
wget -q -O - https://pkg.jenkins.io/debian/jenkins.io.key | sudo apt-key add -
sudo sh -c 'echo deb http://pkg.jenkins.io/debian-stable binary/ > /etc/apt/sources.list.d/jenkins.list'
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 5BA31D57EF5975CA
sudo apt update -y
sudo apt install -y jenkins
sudo systemctl start jenkins
sudo systemctl enable jenkins
```

`chmod +x` the script to make it executable, and then run it to install everything within.

Create AWS Access Keys

Why: AWS Access Keys are necessary for programmatic access to AWS services. These keys will allow Terraform to build infrastucture for our accout, as well as allow Jenkins to prompt Terraform to start building during the Jenkins pipeline deployment.

How:

1.Navigate to the AWS service: IAM (search for this in the AWS console)
2. Click on "Users" on the left side navigation panel
3. Click on your User Name
4. Underneath the "Summary" section, click on the "Security credentials" tab
5. Scroll down to "Access keys" and click on "Create access key"
6. Select the appropriate "use case", and then click "Next" and then "Create access key"
7. The Access and Secret Access keys are needed for future steps, so safe storage of them is vital to a successful automated CI/CD pipeline. Never share your access keys, as a bad actor can get a hold of them and use the keys to access your server, wreaking havoc, compromising data integrity and potentially stealing sensitive information.

---
### Create the Terraform_Docker EC2
- **Why**: Just as in Workload 5, we will use Terraform to provision all the infrastructure necessary to deploy and scale our ecommerce application. In addition to Terraform, however, we will also be using Docker to containerize our app code, creating images via Dockerfile that contains the code necessary to build the frontend of our application (using NodeJS and React to direct network traffic to our Django application) and backend of our application (which will deploy the Django app and make the necessary migrations to our Terraform created PostgreSQL Database). This EC2 will also act as our Jenkins `build-node`, an agent that will be resposible for building the Docker containers for the application, provisioning the infrastructure via Terraform, and cleaning our workspace environment of any unnecessary Docker componets before and after the pipeline deploys the applicaiton. 
  
- **How**: First, we will create the EC2 for Terraform_Docker: 

1. Navigate to the EC2 services page in AWS and click "Launch Instance".
2. Name the EC2 `Terraform_Docker` and select "Ubuntu" as the OS Image.
3. Select a t3.medium as the instance type.
4. Create a new key pair (and be sure to save the .pem somewhere safe!). 
5. In "Network Settings", choose the default VPC selected for this EC2, with Auto-Assign Public IP enabled.
6. Create a Security Group that allows inbound traffic to the services and applications the EC2 will need and name it after the EC2 it will control.
7. The Inbound rules should allow network traffic on ports 22 (SSH) and 8081 (Vscode), and all Outbound traffic.
8. Launch the instance!

Then, we will create and run the below scripts to install Terraform, Docker, VSCode and AWS CLI, as well as Java 17:

**Java-17 Install**
``` bash
#!/bin/bash
sudo apt update -y
sudo apt upgrade -y
sudo apt install -y openjdk-17-jdk
```

`chmod +x` the script to make it executable, and then run it to install everything within.

**Terraform Install:**

```bash
#!/bin/bash
sudo apt-get update && sudo apt-get install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | \
gpg --dearmor | \
sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null
gpg --no-default-keyring \
--keyring /usr/share/keyrings/hashicorp-archive-keyring.gpg \
--fingerprint
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get install terraform
```

Don't forget to `chmod+x` this script as well!

**VSCode Install:**

```bash
#!/bin/bash
curl -L https://code-server.dev/install.sh | sh
sudo systemctl enable --now code-server@$USER
sleep 1
sudo systemctl restart code-server@$USER
CONFIG_PATH="$HOME/.config/code-server/config.yaml"
echo "bind-addr: 0.0.0.0:8081
auth: password
password: <set_your_password>
cert: false" > "$CONFIG_PATH"
```

`chmod +x` this script and run it.

**Docker Install:**

```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
```

```bash
# Install latest build of Docker and Docker plugins (note Compose in there, it'll be important!):
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify Docker works by running the 'hello-world' Image:
sudo docker run hello-world

# Add the Ubuntu user to the Docker group so you can run docker commands with it sudo:
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
```
`chmod +x` it!!

**AWS CLI Install:**

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws --version 

# Configure AWS CLI
aws configure
# You will need to put your access key when prompted
# you'll need to input your secret access key when prompted as well
# Region = "us-east-1"
# output format = "json"
```

After running all those scripts , git clone this repo to your Terraform_Docker EC2.

---
### Add the Terraform_Docker EC2 as a build-node in Jenkins:

**Why:** For all the reasons I addressed in the Jenkins EC2 step! While this seems like a minor improvement over our previous Workload deployments, being able to manage nodes across many different EC2's via a single Jenkins Manager will be instrumental in scaling future Workloads and working in larger teams of engineers. 

**How:**

1. Ensure both the Jenkins and Terraform_Docker EC2s are running and allowing Network connections via their security groups
2. log into the Jenkins UI via `http://<jenkins_ec2_public_ip>:8080` and navigate to the "Build Queue" on the left side of the Dashboard, and then select "Build Executor Status"
3. Select "New Node"
4. Name the node "build-node" and select "Permanent Agent"
5. Here is the information to fill out in the fields on the proceeding page:

```
  i. "Name" should read "build-node"

  ii. "Remote root directory" == "/home/ubuntu/agent"

  iii. "Labels" == "build-node"

  iv. "Usage" == "Only build jobs with label expressions matching this node"

  v. "Launch method" == "Launch agents via SSH"

  vi. "Host" is the public IP address of the Node Server (Terraform_Docker EC2)

  vii. Click on "+ ADD" under "Credentials" and select "Jenkins".

  viii. Under "Kind", select "SSH Username with private key"

  ix. "ID" == "build-node"

  x. "Username" == "ubuntu"

  xi. "Private Key" == "Enter directly" (paste the entire private key of the Jenkins node instance here. This must be the .pem file)

  xi. Click "Add" and then select the credentials you just created.  

  xii. "Host Key Verification Strategy" == "Non verifying Verification Strategy"

  xiii. Click on "Save"
```
6. Navigate back to the "Build Executor Status" and you should now see the `build-node`. Click it, then click "Logs" from the right hand menu and you'll see an output of Jenkins activating the node. If everything worked, the last like of the log output should say the node is "connected and online".

---
### Creating our Docker Images via Dockerfile

**Why:** Containerizing applications gives us a lightweight and more streamlined method of depoying applications that normally would have taken many lines of code and configurations. In this step, we will create two Dockerfiles to create images for the frontend and backend of our appliation - the frontend image building on a base Node image, exposing port 3000 to our EC2 instance, and starting the React proxyserver; the backend image building on a base Python:3.0 image, installing depedencies from the requirements.txt file in the backend directory of this GitHub rep0, running migrations to set up the data migration from the sqlite3.db hosting all the data for the application to the PostgreSQL DB we will create with Terraform, and then running a script that will complete those migrations and launch the Django application that will serve up our Ecommerce website. 

**How:**

run `nano Dockerfile.frontend` and paste this into the new file:

```bash
FROM node:14

WORKDIR /app

COPY ./frontend ./

RUN npm ci

EXPOSE 3000

ENTRYPOINT ["npm", "start"]
```

Next, run `nano Dockerfile.backend` and paste the following into that file:

```bash
FROM python:3.9

WORKDIR /app

COPY ./backend /app

RUN pip install --upgrade pip
RUN pip install django-environ
RUN pip install -r requirements.txt

RUN python manage.py makemigrations account
RUN python manage.py makemigrations payments
RUN python manage.py makemigrations product

RUN chmod +x /app/start_app.sh

EXPOSE 8000

ENTRYPOINT ["./start_app.sh"]
```
More on that `start_app.sh` script later. Next, run `docker login` and login into DockerHub with your credentials, then build the Docker images via the Dockerfiles you just created by running `docker build -t dockerhub_username/repository_name:latest -f Dockerfile.backend/ .` to build the backend image, and then do the same for Dockerfile.frontend to build the frontend image. Finally, use `docker push dockerhub_username/repository_name:tag` to push both of the images to your DockerHub account. Put both of the Dockerfiles in the Terraform directory in this repository. 

---
### Creating our Terraform Infrastructure

## Root Directory

**Why:** This is the big one! Terraform will allow us to spin up the whole infrastructure in one go, provided we have all of our modules, resource blocks, outputs, variables and scripts in order. In the next couple steps, I'll show you how to configure your Terraform files to ensure that everything is correct and you can spin up the infrastructure without issue. Note that I have included all my Terraform files in this GitHub directory, so you could theoretically just git clone this repo and use my already-correct Terraform files to automate the creation of the infrastructure via Jenkins - but I'll give you a high level overview of how everything works so you can do it yourself and forgo my files for learning purposes!

**How:** 

First, navigate to your VSCode terminal by putting this in your address bar: http://<your_ec2_public_ip:8081>

	- Create a directory called Terraform with `mkdir Terraform`
	- In this directory, run `Terraform init` so you can begin running Terraform commands
	- Now let's create the main.tf file. This file will be the telephone board operator for all of your modules - and there will be plenty! As the operator, it deals in connecting variables, not calls - every variable that your other modules need, will first pass through this main.tf before going to the module. It'll all make sense as we go through the module setups. 
	- Your main.tf should look like this. Note the provider block - it's the only place it will appear in your Terraform build, and it will pass along critical variables to your other modules to ensure AWS ties their access together with your access key, allowing you to access all the infrastructure once it's created: 

```hcl
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

Four modules! I know it's all showing up as red in your Vscode terminal right now, but as we create our child directories, corresponding main.tfs and output.tfs, it'll start clearing up!

	- Next, we will create our variables.tf. This will assign the value for many of the variables that we will be passing along to our child directories and Root main.tf. Not all of the variables will have their values declared here, though - some of them will be assigned value as their respective resource is created in the Child directories, and then their value will be routed back to the Root main.tf, where the variable will be placed in the Module block that has to use it. 
	- Take vpc_id for instance. That will not be found in our Root variable.tf, because the id is dependent on the creation of the VPC first. So the VPC will be created, and then in the output.tf of our VPC child directory, we will create the variable and assign it the value of the VPC ID that was created. That is why, in our EC2 Module, it is listed as `vpc_id = module.VPC.vpc_id` - you have to add the path of where the variable was created in the main.tf of the Root module, so that you can properly pass the value to the module that needs it. 
	- Here's the variables.tf for the Root directory:

```hcl
  variable aws_access_key{
    type = string
    sensitive = true
 }                                                    # Replace with your AWS access key ID (leave empty if using IAM roles or env vars)
 
 variable aws_secret_key{
    type = string
    sensitive = true
 }                                        # Replace with your AWS secret access key (leave empty if using IAM roles or env vars)

variable region{
  type = string
}

 variable dockerhub_user{
    type = string
    sensitive = true
 }

  variable dockerhub_pass{
    type = string
    sensitive = true
 }        

 variable instance_type{
  type = string
 }  

variable "frontend_count"{
  type = number
  default = 2
}

variable "backend_count"{
  type = number
  default = 2
}
 variable "db_instance_class" {
  description = "The instance type of the RDS instance"
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "The name of the database to create when the DB instance is created"
  type        = string
  default     = "ecommerce"
}

variable "db_username" {
  description = "Username for the master DB user"
  type        = string
  sensitive = true
}

variable "db_password" {
  description = "Password for the master DB user"
  type        = string
  sensitive = true
}

variable "alb_name" {
  default = "frontend-backend-alb"
}

variable "backend_port" {
  default = 8000
}

variable "frontend_port" {
  default = 3000
}
```

With this variables.tf in front of you, can see what I mean by passing a variable that was outputted by a Child directory to the main.tf, and passing one that is created in the root variables.tf. Take for instance the `instance_type` variable in our EC2 module - Instead of using a module path when assigning the value, since we have it in our Root variables.tf file, we use `instance_type = var.instance_type`, referencing the value in the Root variables.tf instead. 

- The next terraform file we need here is an important one - terraform.tfvars. This file will pass along variables that we've labelled as "secret" in our variables.tf file. These variables are ones that we do not want publicly accessible, lest they could fall into the hands of a bad actor - files like our access_key and secret access_key. We will add this into our Jenkins file via Jenkins Credential Manager once we get to that step! 
- Here's what it should look like:

```hcl
aws_access_key = "your_access key"       
aws_secret_key = "your_secret_key"
instance_type = "t3.micro"
db_username = "your_db_username"
db_password = "your_db_password"
dockerhub_user = "your-dh-username"
dockerhub_pass = "your-dh-password"
```

This will help us automate the build without compromising our security!

- Now, we will work on scripts! We will write two scripts: one named `deploy.sh` that will be called into the `user_data` portion of our ecommerce_app EC2 servers, running once Terraform creates them; and a compose.yml that will also be called into the same user_data section and be used to create the `docker-compose.yml` file in our app EC2's, so that the Docker containers can be created and launch our Ecommerce webapp. This is in the "Root Directory" section of the readme, because it's easier to path the files to the user_data field if they are in the root directory. 
- Here is our first user_data script: `deploy.sh`

```bash
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
```

This script will update the servers, install node exporter on them (necessary for out monitoring server to collect metrics from the server post deployment), install docker (as well as docker-compose), log into your DockerHub account, create the docker-compose.yml by catting the one we are piping into the User_Data section of the EC2's and copying it's contents, and then creating our frontend/backend docker images and containers via the two `docker compose` commands, and then finally cleaning up our server environment by pruning the cache and containers from the server and logging out of our DockerHub session.

- Next, we will create the compose.yml file:

```bash
version: '3.8'

services:
  backend:
    image: dh_username/backend-image_name:latest
    environment:
      - DB_HOST=${rds_endpoint}
      - RUN_MIGRATIONS=${run_migrations}
    ports:
      - "8000:8000"

  frontend:
    image: dh_username/frontend-image_name:latest
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

The compose.yml file will create two containers based on our frontend and backend images (pulled from DockerHub). They will be called `backend` and `frontend` respectively. Note the Environment Varialbes in the backend service portion - these will pass `rds_endpoint` and `run_migrations` variables set in our User_Data to the backend container - crucial for migrating the data in the sqlite3.db to our postgreSQL db once it's created by Terraform. 

- Our final script will be the `start_app.sh` script. This won't be located in our Terraform root directory, but rather in the backend directory of the GitHub repository. This script will ensure that the migrations are only run on the backend container of one of the App EC2's, rather than both. If the migrations ran twice, then one of the EC2's would run into duplicate record issues within the database, and it would result in our ecommerce web application only working in one AZ. 
- Here's the script:

```bash
#!/bin/bash

set -e

if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations..."
    python manage.py migrate
    python manage.py dumpdata --database=sqlite --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 4 > datadump.json
    python manage.py loaddata datadump.json
    rm -f db.sqlite3
else
    echo "Already Migrated!"
fi

python manage.py runserver 0.0.0.0:8000
```

That's all for the root directory! Now, for our first module - the VPC!

---
## Child Directory - VPC

**Why:** The first child directory we will create is for VPC, which will correspond with our VPC module in the root main.tf. We will make this as a sub-directory of our Terraform directory, and then we will create 3 Terraform files in that sub-directory: main.tf, variables.tf and outputs.tf. `main.tf` will be where we create the various resource blocks we will need for our VPC to function correctly across multiple AZ's, it'll create our 2 public and 2 private subnets, their route tables, and the Internet Gateway and NAT Gateway that will be associated with them. There will also be resource blocks to create VPC peering connection between our Default VPC (which houses the EC2's we've already made, as well as our Monitoring EC2 we will make later), as well as associating that Peering Connection with the Public and Private Route Tables that will be created by Terraform. Then, we will create an outputs.tf, which will output the value of variables that are associated with parts of the VPC infrastructure, to be used in our other child directories - this is why our VPC gets built first, as it has the most output variables that our other modules will rely on. It also does not need to declare any variables from our Root or other modules, so that's another reason to create it first!

**How:** Let's start with the main.tf. Create a new file in the newly created `VPC` directory called `main.tf`, and model it after my main.tf file below:

```hcl
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
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "172.31.0.0/16"            
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}

resource "aws_route" "private_peer_route" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "172.31.0.0/16"            
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}

resource "aws_route" "default_peer_route" {
  route_table_id         = "rtb-0adb5c3fb76733aae"             
  destination_cidr_block = aws_vpc.main.cidr_block    
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}
```

There's a ton of important resource blocks in there! I broke down most of their use cases in there, and you can ascertain the need for the rest from my previous Workload 4 deployment. 

- Now, let's create the outputs.tf file. Create a new file in the `VPC` directory called `outputs.tf`, and model it after my file below:

```hcl
output "vpc_id" {
    value = aws_vpc.main.id
}

output "public_subnet"{
    value = [for subnet in aws_subnet.public : subnet.id]
}

output "private_subnet"{
    value = [for subnet in aws_subnet.private : subnet.id]
}
```

These output variables will be used in basically all our other modules, so it's great that we have them outputted first! That's all for our VPC child directory, so let's build out the next one - possibly our most important - the EC2 child directory!

---
## Child Directory - EC2

**Why:** Next up: our EC2 Module. Create the Child directory for the EC2 in the same manner as the VPC - navigate back to the root `Terraform` directory, and then create a new directory called `EC2`. We'll then create a main.tf, outputs.tf, and this time, a variables.tf as well to list the variables we will need to declare and pass into our EC2 module to assist in the building out of our EC2 instances, security groups, and other components.

**how:** Let's start with the main.tf file. While in the `EC2` child directory, create a file called `main.tf` and model it after the one I have below:

```hcl

resource "aws_instance" "backend_server" {
  count = var.backend_count
  ami = "ami-0866a3c8686eaeeba"                # The Amazon Machine Image (AMI) ID used to launch the EC2 instance.
                                        # Replace this with a valid AMI ID
  instance_type = var.instance_type                # Specify the desired EC2 instance size.
  # Attach an existing security group to the instance.
  # Security groups control the inbound and outbound traffic to your EC2 instance.
  vpc_security_group_ids = [aws_security_group.backend_sg.id]         # Replace with the security group ID, e.g., "sg-01297adb7229b5f08".
  key_name = "WL6"                # The key pair name for SSH access to the instance.
  subnet_id = var.private_subnet[count.index % length(var.private_subnet)]
user_data = base64encode(templatefile("${path.root}/deploy.sh", {
    rds_endpoint = var.rds_endpoint,
    docker_user = var.dockerhub_user,
    docker_pass = var.dockerhub_pass,
    pub_key = local.pub_key,
    docker_compose = templatefile("${path.root}/compose.yml", {
      rds_endpoint = var.rds_endpoint,
      run_migrations = count.index == 0 ? "true" : "false"
    }),
  }))

  # Tagging the resource with a Name label. Tags help in identifying and organizing resources in AWS.
  tags = {
    "Name" : "ecommerce_app_az${count.index +1}"         
  }

  depends_on = [
    var.postgres_db,
    var.nat_gw
  ]
}

resource "aws_instance" "frontend_server" {
  count = var.frontend_count
  ami = "ami-0866a3c8686eaeeba"                # The Amazon Machine Image (AMI) ID used to launch the EC2 instance.
                                        # Replace this with a valid AMI ID
  instance_type = var.instance_type                # Specify the desired EC2 instance size.
  # Attach an existing security group to the instance.
  # Security groups control the inbound and outbound traffic to your EC2 instance.
  vpc_security_group_ids = [aws_security_group.frontend_sg.id]         # Replace with the security group ID, e.g., "sg-01297adb7229b5f08".
  key_name = "WL6"                # The key pair name for SSH access to the instance.
  subnet_id = var.public_subnet[count.index % length(var.public_subnet)]
 user_data = templatefile("kura_key_upload.sh", {
       pub_key = local.pub_key
  })
  # Tagging the resource with a Name label. Tags help in identifying and organizing resources in AWS.
  tags = {
    "Name" : "ecommerce_bastion_az${count.index +1}"         
  }

   depends_on = [
    var.postgres_db,
    var.nat_gw
  ]
}

# Create a security group named "tf_made_sg" that allows SSH and HTTP traffic.
# This security group will be associated with the EC2 instance created above.
resource "aws_security_group" "frontend_sg" { # in order to use securtiy group resouce, must use first "", the second "" is what terraform reconginzes as the name
  name        = "tf_made_sg"
  description = "open ssh traffic"
  vpc_id = var.vpc_id
  # Ingress rules: Define inbound traffic that is allowed.Allow SSH traffic and HTTP traffic on port 8080 from any IP address (use with caution)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

     ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    }

  # Egress rules: Define outbound traffic that is allowed. The below configuration allows all outbound traffic from the instance.
 egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  # Tags for the security group
  tags = {
    "Name"      : "Bastion_SG"                          # Name tag for the security group
    "Terraform" : "true"                                # Custom tag to indicate this SG was created with Terraform
  }
}

resource "aws_security_group" "backend_sg" { # in order to use securtiy group resouce, must use first "", the second "" is what terraform reconginzes as the name
  name        = "tf_made_sg_private"
  description = "host gunicorn"
  vpc_id = var.vpc_id
  # Ingress rules: Define inbound traffic that is allowed.Allow SSH traffic and HTTP traffic on port 8080 from any IP address (use with caution)
   
   ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    } 

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    }   

 ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    }

  ingress {
    from_port   = 9100
    to_port     = 9100
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    }

     egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

 # Tags for the security group
  tags = {
    "Name"      : "App_SG"                          # Name tag for the security group
    "Terraform" : "true"                                # Custom tag to indicate this SG was created with Terraform
    }
}

  resource "aws_security_group_rule" "backend_to_rds_ingress" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.backend_sg.id
  source_security_group_id = var.rds_sg_id
}

resource "aws_security_group_rule" "allow_alb_to_frontend" {
  type              = "ingress"
  from_port         = var.frontend_port
  to_port           = var.frontend_port
  protocol          = "tcp"
  security_group_id = aws_security_group.backend_sg.id  

  source_security_group_id = var.alb_sg_id  
}


output "instance_ip" {
 value = [for instance in aws_instance.frontend_server : instance.public_ip]  # Display the public IP address of the EC2 instance after creation.
}
```

First thing I want to draw your attention to in this EC2 main.tf is the count parameter. Count allows us to dynamically scale the amount of EC2's created by Terraform. I have mine set to a variable, so I can easily change the count anywhere the variable is referenced (I have it set to 2). You'll see `[count.index]` sprinkled around the file as well - that allows us to make changes to each front_end and back_end server that is created via the count argument by iterating through the each item in the count. 

Next, look at the user_data fields in each of the EC2 instance resource blocks. We've already gone over there function - to run scripts at the inception of the EC2 instances - but let's talk about how we're doing some of that. The user_data file uses a templatefile() to pass variables declared in Terraform to the script, so that they can be used to run necessary commands in the script, such as passing the compose.yml file as a variable to be used in our `deploy.sh` script, or our dockerhub credentials so we can pull our frontend and backend images into the `docker-compose.yml` once it is created. Notice how we leverage count.index to run a boolean to determine which EC2 the migrations will occur in - `count.index ==  0 ?` sets a conditional, where if the first EC2 is created (the first one being 0), then the docker backend container created on that EC2 will migrate all the tables from sqlite.db to postgresql. The second will register as FALSE to the expressio since the first EC2 already exists, and the migrations will thus not run on the second EC2. This helps us avoid the issue of data redundancy in our new DB. 

Last thing to look at - depends_on! We use depends_on to control when our resources are created, in relation to whether or not a different resource it is reliant on is already created. For our EC2 module, we have `depends_on` in two resource blocks - our app and bastion servers both depend on the existence of the RDS (so that the user_data scripts have a DB to migrate the data into), and NAT Gateway being created first, so that we can login into DockerHub and pull our docker images as needed by the `deploy.sh` script. Are you starting to see the power and modularity of Terraform yet?

Let's just go over the security groups quickly. We have two security groups - one for both of our frontend servers, and one for both of our backend servers. Unlike workload 5, both the frontend and backend portions of our application are situated in the app_server EC2, so our security groups reflect that change, allowing network traffic straight to the app_servers.  Our bastion servers have these ports open: 22 for SSH, 80 for http access, and we have all ports open for egress. These servers are meant only for us engineers to connect to the app_server to observe any issues and perform maintenance when needed. Our app servers have port 22 open, again for SSH, port 8000 open for our Django application, and port 9100 for Node Exporter (I know you missed monitoring!). We have two special resource blocks for specific securtiy group allow rules - one that opens port 5432 on our app servers to allow our RDS to send and receive data from the backend_servers, and one that explicitly allows our Application Load Balancer to direct network traffic to our app server's React proxy-server on port 3000. 

 - Alright, with the main.tf out the way, let's create our variables.tf file. In your `EC2` child directory, create a new file, call it `variables.tf`, and model it after my file below:

```hcl
 variable region{
 }     

 variable instance_type{
 }  

 variable "vpc_id"{
 }

 variable "public_subnet"{
 }

 variable "private_subnet"{
 }

 variable "frontend_count"{
 }

 variable "backend_count"{
 }

 variable "db_name"{
 }

 variable "db_username"{
 }

 variable "db_password"{
 }

 variable "rds_address"{
 }

 variable "rds_endpoint"{
 }

 variable "postgres_db"{
 }

variable "rds_sg_id" {
 }
 
variable "alb_sg_id"{
}

variable "frontend_port"{
}

variable "dockerhub_user"{
}

variable "dockerhub_pass"{
}

variable "nat_gw"{
}
```

As you may have been able to tell just by looking at the EC2 main.tf, there are many variables that we have to declare in order to make our EC2's function correctly and connect to the many different components of our Terraform-created infrastructure, the most out of any of our variables.tf. It's pulling variables from every single other module in the Terraform directory structure, which makes sense if you think about - the EC2's are where all the action happens, where the application is deployed and network traffic to it is handled, so it would need to be able to interface with every other part of our ecosystem. 

- And finally, our outputs.tf file. Not too many in this one. Create a new file called `outputs.tf` in your EC2 child directory, and model it after my file below

```hcl
output "backend_sg_id" {
    value = aws_security_group.backend_sg.id
}

output "frontend_server_ids" {
  value = [for instance in aws_instance.frontend_server : instance.id]
}

output "backend_server_ids" {
  value = [for instance in aws_instance.backend_server : instance.id]
}
```

This will allow our other modules to use these variables to create and deploy their respective parts of the infrastructure.

---
## Child Directory - RDS

**Why:** We are migrating all the data in our source code's sqlite.db from that lightweight database to PostgreSQL, managed by Amazon RDS, for numerous reasons: PostgreSQL is capable of handling concurrent connections, crucial for an ecommerce website deployed across multiple AZ's; it supports advanced data types, such as JSON arrays, which aids tremendously in manipulating the data stored in its tables; and leveraging RDS allows us to use the DB as a single source of truth for both of our instances of the Django application, allowing us to safely manipulate all the data that comes in through our ecommerce website. 

**How:** The how is the same as the last 2 child directories, so we'll speed through this one. Navigate back to the `Terraform` root directory, create a new directory called `RDS`, and cd into there. 

- Here's our main.tf file below for the RDS Child directory - model yours after it:

```hcl
resource "aws_db_instance" "postgres_db" {
  identifier           = "ecommerce-db"
  engine               = "postgres"
  engine_version       = "14.13"
  instance_class       = var.db_instance_class
  allocated_storage    = 20
  storage_type         = "standard"
  db_name              = var.db_name
  username             = var.db_username
  password             = var.db_password
  parameter_group_name = "default.postgres14"
  skip_final_snapshot  = true

  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  tags = {
    Name = "Ecommerce Postgres DB"
  }
}

resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "rds_subnet_group"
  subnet_ids = var.private_subnet

  tags = {
    Name = "RDS subnet group"
  }
}

resource "aws_security_group" "rds_sg" {
  name        = "rds_sg"
  description = "Security group for RDS"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "RDS Security Group"
  }
}

resource "aws_security_group_rule" "rds_ingress" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds_sg.id  
  source_security_group_id = var.backend_sg_id            
}
```

- Here's our variables.tf file for the RDS Child directory - model away!:


```hcl
variable "db_instance_class" {
}

variable "db_name" {
}

variable "db_username" {
}

variable "db_password" {
}

 variable "private_subnet"{
    type = list(string)
 }

 variable "vpc_id"{
 }
 
 variable "backend_sg_id" {
 }
```

- And finally, here's our outputs.tf for the RDS Child directory - feel free to use it:


```hcl
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
```
---
## Child Directory: ALB

**Why:** We are again provisioning an Application Load Balancer for this workload, so we can simultaneously serve to different AZ's without overloading the infrastructure in any given one. The Application Load Balancer is the gateway to our Django application - it will be the first point of contact for all network traffic trying to reach our application, and it will route that traffic to the most available app_server to that client, cutting down on network lag for the user and allowing us to better manage our resources. If one of the frontend servers go down, it will route the traffic to the other server, maintaining availability to our application and increasing it's overall resiliency. This is what being a DevOps engineer is all about!

**How:** The how is just like the other three Child directories, so we'll make this quick. Return to your `Terraform` Root directory, create a new directory called `ALB`, and let's start making our final batch of terraform files!

- First, the main.tf file for the ALB Child directory - model yours after it:

```hcl

resource "aws_security_group" "alb_sg" {
  name   = "alb_sg"
  vpc_id = var.vpc_id

  ingress {
    description = "Allow HTTP traffic"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

   ingress {
    description = "Allow HTTP traffic"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }


  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


resource "aws_lb" "frontend_alb" {
  name               = var.alb_name
  internal           = false  
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = var.public_subnet

  enable_deletion_protection = false
}

resource "aws_lb_target_group" "frontend_tg" {
  name     = "frontend-target-group"
  port     = var.frontend_port
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    protocol            = "HTTP"
    path                = "/health"  
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 2
  }
}

resource "aws_lb_target_group_attachment" "frontend_tg_attachment" {
  count            = var.frontend_count  
  target_group_arn = aws_lb_target_group.frontend_tg.arn
  target_id        = var.backend_server_ids[count.index]  
  port             = var.frontend_port  
}

resource "aws_lb_listener" "http_listener" {
  load_balancer_arn = aws_lb.frontend_alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend_tg.arn
  }
}

output "alb_dns_name" {
  value = aws_lb.frontend_alb.dns_name
  description = "KuraCommerce"
}

- Next, our variables.tf for the ALB Child Directory:

```hcl
variable "alb_name"{
}

variable "backend_port"{
}

 variable "frontend_count"{

 }
 variable "frontend_port"{
   
 }
variable "backend_count"{
}

variable "frontend_server_ids"{
}

variable "backend_server_ids"{
}

variable "public_subnet"{
}

variable "vpc_id"{
}
```

And the final outputs.tf file:

```hcl
output "alb_sg_id"{
    value = aws_security_group.alb_sg.id
}
```

And that's all for Terraform! In your Terraform root directory, run a `terraform validate` command to ensure all the pieces are correctly placed, all variables are being outputted and called correctly, and there are no issues with syntax. If that passes, then run a `terraform plan` command so you can see the blueprint of every piece of infrastructure that will be created, right in your terminal. And once you are satisfied with that, it's time to build: run `terraform apply` and watch the magic happen! It'll take around 10 mins to provision all the infrastructure, but if it worked correctly, then you should be able to navigate to AWS, find your Load Balancer DNS address, and put that in your address bar to connect to the ecommerce website! If you see all the products available for purchase, then congrats, you did it correctly!

Now, tear it all down with `terraform destroy`! It's time to really automate this deployment, with - drum roll please - Jenkins!

---
## Jenkins Pipeline

**Why:** Jenkins is going to take this deployment over the top, building the source code, testing it thoroughly, and then running it's own terraform commands to build and deploy the infrastructure, all in one go!

**How:**  Return to the Jenkins UI, create a multi-branch pipeline, add your GitHub Credentials to it, and then - WAIT! Before we can initiate the Jenkins pipeline, we need to add our DockerHub credentials to Jenkins Credential Manager so the Jenkins user can log into DockerHub on our behalf and build the containers necessary for our Ecommerce app to function. To do so: 

	1. Navigate to the Jenkins Dashboard and click on "Manage Jenkins" on the left navagation panel.
	2.  Under "Security", click on "Credentials".
	3.  You should see the GitHub credentials you just created here.  On that same line, click on "System" and them "Global credentials (unrestricted)". (You should see more details about the GitHub credentials here (Name, Kind, Description))
	4.  Click on "+ Add Credentials"
	5.  In the "Kind" Dropdown, select "username and password"
	6.  Under "username", put your DockerHub Username.
  7.  Under "password", put your Dockerhub password.
	8.  Under "ID", put "docker_hub_credentials" (without the quotes)
	
Jenkins is taking these credentials, storing and encrypting them for use within the Jenkinsfile as environmental variables. We use these by adding an environment parameter at the very beginning of our Jenkinsfile, and declaring the credentials there, as well as assigning them to a variable. This variable will be used througout our Jenkinsfile, whenever we need to pull an image from DockerHub. This will maintain your accounts security, hiding privileged access from the world while exposing control to the Jenkins Pipeline. This is why I similarly created a Credential "secret file" variable for my `terraform.tfvars` file, passing that into the Jenkins pipeline with the"withCredentials" argument so that jenkins would have everything it needs to build the infrastructure via Terraform. I suggest you do the same! 

Now, time to run the Jenkins pipeline.  My Jenkinsfile has 5 stage to it:

1. Build Stage - This will install and build out the dependencies for both our front and backend servers, ensuring everything needed for the application to function is included in the GitHub Repo.

2. Test Stage - Here, we conduct Django pytests on our backend application code to make sure it works properly and everything is in place for the DB migration from Sqlite.db to PostgresSQL.

3. Cleanup Stage - This is the first stage utilizing the "build-node" agent, meaning it will be taking place on our Terraform_Docker EC2, rather then the Jenkins EC2 as the last two stages did. All the stages from here on out will be done via the build-node. This stage will clean the TF_Docker EC2 of any cached or otherwise unused Docker components, readying it for the Docker build stage. 

4. Build & Push Images Stage - Here is the first stage where we call DockerHub credentials via our variables to log into DockerHub. This stage will build our front/backend Docker images via our Dockerfiles and push them to DockerHub, ensuring any changes we made to the DockerFiles since we manually deployed the application have been logged to DockerHub, allowing Jenkins to build the most up-to-date version of our Ecommerce application.  

5. Infrastructure Stage - Here's the stage where Terraform works it's magic! If you uploaded your .tfvars file as a secret file in Jenkins Credential Manager, now is the time to use it - otherwise, Jenkins will be prompted to input the strings that are decalred by hidden in your variables.tf file. You'll also need to use the docker_hub variable for username and password again if you didn't upload your .tfvars. This stage will take about 10 mins, as Jenkins prompts Terraform to build out the infrastructure.

6. Post - The final stage in our Jenkinsfile, this one will run regardless of whether the others stages passed or failed. This stage will perform the same functions as the cleanup stage, pruning stale Docker components from our TF_Docker EC2 to conserve space and memory, as well as logging out of our DockerHub account. 

Now, navigate to your Load Balancer DNS again, put it in your address bar, and if you see the ecommerce website and all the products then voila - we have successively completed our second truly automated deployment, and our first deploying a containirized application!

---
## Monitoring

**Why:** We need to monitor our app servers to ensure that they aren't being overwhelmed by traffic or meddled with by bad actors. 

**How:** First, create a t3.micro for the monitoring apparatus and name it "Monitoring". It's inbound rules should allow network traffic on Ports 22 (SSH), 9090 (Prometheus), 3000 (Grafana), and allow all Outbound traffic. Choose the same VPC as your Terraform_Docker EC2. In Workload 5, I had a lengthy section about setting up VPC peering here, but since we automated the peering connection from the VPC the monitoring EC2 is in to the Terraform created VPC this time, we're all set! SSH into your Monitoring EC2 and follow these steps to install Prometheus, Grafana, and configure Prometheus to scrape metrics from both of your app servers.

**1. Install Prometheus**:
```bash
sudo apt update
sudo apt install -y wget tar
wget https://github.com/prometheus/prometheus/releases/download/v2.36.0/prometheus-2.36.0.linux-amd64.tar.gz
tar -xvzf prometheus-2.36.0.linux-amd64.tar.gz
sudo mv prometheus-2.36.0.linux-amd64 /usr/local/prometheus
```

**2. Create a service daemon for Prometheus**:
To ensure Prometheus starts automatically:
```bash
sudo nano /etc/systemd/system/prometheus.service
```
Add the following to the file:
```bash
[Unit]
Description=Prometheus Monitoring
After=network.target

[Service]
User=prometheus
ExecStart=/usr/local/prometheus/prometheus \
--config.file=/usr/local/prometheus/prometheus.yml \
--storage.tsdb.path=/usr/local/prometheus/data
Restart=always

[Install]
WantedBy=multi-user.target
```
**3. Start and enable the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl start prometheus
sudo systemctl enable prometheus
```

**4. Install Grafana**:
Add the Grafana APT repository:
```bash
sudo apt install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add
sudo apt update
sudo apt install -y grafana
```
**5. Start and enable Grafana:**
```bash
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

Prometheus will scrape system metrics from both of the app EC2's (through Node Exporter) for monitoring purposes. The `prometheus.yml` file needs to be updated to include the private IP of the both EC2's as a target to ensure Prometheus pulls data from them. By default, Node Exporter exposes metrics on Port 9100, hence why we had to add an Inbound Rule to our Backend EC2's security group to allow traffic on Port 9100. Without this rule in place, Prometheus would be unable to collect the metrics exposed by Node Exporter. This is also why we needed to enable VPC Peering for our VPCs and add the Peering Connection to the Private Subnet Route Table - without that step, the `Monitoring` EC2 would be unable to communicate to the Private IP of the App EC2's. 

- **How**:
  
**1. Edit the `prometheus.yml` file**:

```bash
sudo nano /usr/local/prometheus/prometheus.yml
```

Add the following section under `scrape_configs` to target the 'Application_Server' EC2:
```bash
scrape_configs:
         - job_name: 'jenkins'
           static_configs:
             - targets: ['<Pivate_IP_of_App_Server1_EC2>:9100']
```
Then do the same thing to add App Server 2 as a target

**2. Restart Prometheus to apply the changes:**

```bash
sudo systemctl daemon-reload
sudo systemctl restart prometheus
```

---
### Add Prometheus as a Data Source in Grafana and Create Dashboards

- **Why**: Once Prometheus is scraping metrics, Grafana provides a user-friendly way to visualize the data. Creating a dashboard with graphs of system metrics (like CPU usage, memory usage, etc.) enables easy monitoring and helps track the health of the App EC2's in real time. This ensures that the App Servers operate smoothly and that any issues are quickly identified before they impact the application's performance or availability.

- **How**:
  
**1. Add Prometheus as a data source in Grafana**:
  - Open Grafana in the browser: `http://<Monitoring_Server_Public_IP>:3000`
  - Login with default credentials (`admin/admin`).
  - Navigate to **Configuration > Data Sources**, click **Add data source**, and select **Prometheus**.
  - In the **URL** field, enter: `http://localhost:9090` (since Prometheus is running locally on the Monitoring EC2).
  - Click **Save & Test**.

**2. Create a dashboard with relevant graphs**:
  - Go to **Dashboards > New Dashboard**.
  - Select **Add new panel**, and choose **Prometheus** as the data source.
  - Select "Import a Dashboard" and download this: https://grafana.com/grafana/dashboards/1860-node-exporter-full/
  - Drag the downloaded dashboard to the dropbox for Importing Dashboards
  - Save the dashboard with an appropriate name (e.g., **App Server Monitoring**).
---
## System Diagram

[WL6_Diagram](https://github.com/tortiz7/ecommerce_docker_deployment/blob/main/Diagram.jpg)

---
## Issues/Troubleshooting

### Issue With Database migrations running on both backend Docker containers:

**Problem:** Just as we encountered in Workload 5, the User_Data files we have running in our App EC2 resource block indeed run on both of the EC2's that are spun up by Terraform. This is an issue, because we cannot have duplicate data in our PostgreSQL database; this leads to the products only showing up on our Ecommerce website on one AZ, with the other AZ lacking the products because it could not establish a connection to the Database. To fix this, I had to ensure the Migrations only ran on one of the App EC2's Backend containers. 

**Solution:** My first attempt at a solution was adding the if/then statement that is now in the `start_app.sh` script (found in the backend repository) directly to the compose.yml file. The compose.yml file initially had the migrations written in there, so I thought adding an if/then conditional to those migration commands would be no sweat. That was not the case, however - passing the `run_migrations` variable into the shell command chain in the compose.yml proved nigh-impossible. This is because the variable gets processed first by Docker Compose, then interpreted by the invoked shell environment in compose, and this double interpretation proved fatal towads my plan. I therefore pivoted to using the `start_app.sh` solution instead, avoiding the bash shell-in-docker-compose conundrum entirely. 

### Test Stage Failing in the Jenkins Pipeline:

**Problem:** The commands in the Test stage for my Jenkinsfile is virtually the same as the one from Workload 5, which I believed would not be an issue because we are working with the same Ecommerce Django application source code. The commands were indeed not the issue - the issue was the files present in the GitHub repository. The Jenkins pipeline Test Stage initates the tests via the `tests.py` file in the backend/account directory of the repo, which evalautes records in the database. The Test Stage was attempting to evaluate records in the PostgreSQL database though, which does not exist during Test stage - it is created during Infrastructure stage of the Jenkins Pipeline. 

**Solution:** The solution was twofold. First off, the `pytest.ini` file that was present in the backend repository of the previous Workload was no longer present in this one, so I had to create that. The `pytest.ini` file sets the Django environment variable for the test, pointing the pytest to where the test file is. The second fix was changing the default database used for the pytest - in Workload 5, I used sed commands to comment out the PostgreSQL Databse information in the settings.py file, forcing the pytest to use the sqlite3.db for the test instead, where all of our app data resides before we migrate it to the Terraform-created PostgreSQL DB. This time aroud, I created a separate `settings.py` file called `settings_test.py` in the same folder as the `settings.py` file, where we import all settings from the `settings.py` EXECEPT for the DB information - instead, we set the default database to the sqlite3.db one, allowing our Pytest to work without issue. Moral of the story - always thorough look through ANY GitHub repository you inherit, even ones that look identical to repos you've worked with before!

### `Post` Stage Always Failing
**Problem:** Initially, I could not get the final `Post` step in my Jenkinsfile to work. While the `Post` step failing did not stop my Ecommerce application from deploying successfully, it did make my Jenkins Pipeline output a glaring 'FAILURE' message upon completion, which did not sit well with me. My first instinct was to implement a workaround - just change the `Post` step to a normal Stage, that I called `Final Cleanup`, which carried out the same steps on my `build-node` EC2 as the `Post` step. There was a much easier solution, however. 

**Solution:** The issue was simply syntactic - I was trying to tell the `Post` step to initalize cleanup on the `build-node` the same way as I do for the rest of the Jenkins pipeline, with `agent { label 'build-node' }`. This is incorrect when working with a `Post` step, however - the correct syntax is `node('build-node')`. This simple Syntax (and parenthetical) error was resulting in the error. So, to conclude - Always look up documentation when you're stuck! The issue tends to be simplier than it initally appears. 

### Missing Images for the Products in the Database
**Problem:** Once I successfully migrated all the data from the sqlite3.db to the PostgreSQL DB and deployed the Ecommerce application, I navigated to the Ecommerce website via the Load Balancer DNS and was dismayed to find that about half of the products were missing images!

**Solution:** This was an easy fix - since the products were exactly the same as the ones found in the database for the Ecommerce Application in our last Workload, I just downloaded the folder containing those images (backend/static/images), and uploaded them to the same folder in my current GitHub Repository, replacing the ones that were already there and adding the ones that were missing. Again - make sure you thoroughly look at every folder in a GitHub repository you are working with!

---
## Optimizations

**Optimize Load Balancer Health Checks**

I could not get the health check function for my ALB to work. I would like to Fine-tune health check intervals and thresholds to ensure efficient failover and traffic routing while reducing unnecessary health check requests that could impact performance and costs.

**Implement Auto-scaling for EC2 Instances**

Using auto-scaling policies based on CPU, memory, or network thresholds to automatically adjust the number of backend servers will make the infrastructure more resilient. This would aslo maintains availability and reduces costs by only provisioning the required resources. 

**Cloudwatch Implementation**

Switching from Prometheus and Grafana to the AWS managed service CloudWatch can lead to quicker, automated metric gathering and analysis on our and Application servers, as well as our Docker Containers, and can lead to less downtime should the servers encountering an issue or otherwise be rendered offline. Finetuned alarms would ensure that we are always aware of the health of our servers.

**Handling Database Migrations with Idempotency**

Rather than running the database migrations in the Dockerfile.backend container, we can designate a specific container that is only deployed once and runs the migrations prior to the creation and deployment of the backend containers onto our EC2's. This would avoid the migration running more than once without the need for our boolean variable and additional scripting, ensuring Idempotency for our migrations. 

**Disaster Recovery Plan**

We can (and should!) automate snapshots of our PostgreSQL DB so that we can easily back them up and use them for recovery operations should our database become corrupt or otherwise compromised. We can tag these snapshots by date or some other classifer so we can have a better idea of the contents of that snapshot, or even dump the database periodically into an S3 bucket to better sift through it's contents, or just dump RDS logs into that bucket for more targeted maintenance. 

---
## AI Model: Fraud Detection Analysis and Implementation

### Overview

On top of creating the infrastrucutre for our Ecommerce application via Terraform and Jenkins, and containirizing the application via Docker, I was also tasked with creating a machine learning AI model that could assist in detecting fradulent transactions occuring on our Ecommerce website. Think of fraud detection like finding a needle in a digital haystack - we need the right tool for the job. To find the perfect model, I implemented and compared three machine learning approaches for detecting fraudulent transactions: Isolation Forest (our eventual winner), DBSCAN (Density-Based Spatial Clustering), and Autoencoders. After thorough analysis and optimization, Isolation Forest emerged as the optimal solution - providing the perfect balance of accuracy and efficiency, much like a well-calibrated metal detector rather than digging through the entire haystack by hand. To read the full Readme for the AI portion of this project, please navigate here:

---
## Conclusion

By leveraging Docker containers, Terraform Infrastructure as Code, Jenkins CI/CD, and a multi-AZ architecture, we've transformed a traditional deployment into a robust, scalable cloud ecosystem. This workload represents more than a technical upgrade—it's a strategic approach to cloud-native development that prioritizes flexibility, security, and operational excellence. Through containerization, infrastructure automation, and intelligent multi-subnet design, we've created an application infrastructure that can dynamically adapt, scale, and maintain high availability. This is a vast improvement on even the last Workload I've shared with you - and symbolized a huge evolution in my abilities as an engineer. 

This implementation transcends traditional deployment methodologies, embodying a comprehensive DevOps philosophy that integrates Jenkins for continuous integration and delivery, precise resource management, and holistic monitoring. This project serves as a blueprint for modern cloud engineering, demonstrating how infrastructure can be treated as code, containers can become deployment units, and automation can drive operational efficiency. The result is not just an e-commerce application, but a resilient, future-proof system ready to meet the demanding challenges of contemporary cloud computing.

---
## Documentation


![WL5_Website](https://github.com/user-attachments/assets/12ae5e37-e848-4685-a051-db22ed91aa10)


![WL6_AppServer1_Grafana](https://github.com/user-attachments/assets/a06bf5d1-59f9-45db-ba94-6518d05ed8fa)


![WL6_AppServer2_Grafana](https://github.com/user-attachments/assets/d30ae59a-6582-49f9-9aee-993a93256591)


![WL6_Jenkins_Pipeline_Console](https://github.com/user-attachments/assets/c3a5f7bb-2590-48b8-9883-19e08d3f2054)


![WL6_Jenkins_Pipieline_Success](https://github.com/user-attachments/assets/e1e2e490-e97e-4fb2-9d89-d0c49c21c4b7)











