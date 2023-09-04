# A Ubuntu based Docker image with the following installed:
# - Python 3
# - pip3
# - PowerShell Core
# - curl
# - zip and unzip

FROM ubuntu:22.04

# Update oneself
RUN apt-get update && apt-get upgrade -y

# Install Python 3
RUN apt-get install -y python3 python3-pip
# Upgrade pip
RUN pip3 install --upgrade pip

# Install PowerShell Core
RUN apt-get install -y wget apt-transport-https software-properties-common
RUN wget -q https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb
RUN dpkg -i packages-microsoft-prod.deb
RUN rm packages-microsoft-prod.deb
RUN apt-get update && apt-get install -y powershell

# Install curl
RUN apt-get install -y curl

# Install zip and unzip
RUN apt-get install -y zip unzip

# Add the Python modules
RUN pip3 install --upgrade PyYAML

WORKDIR /app/cmd/beats/scriptablebeat/

COPY . .

# Set the entrypoints executable
RUN chmod +x /app/cmd/beats/scriptablebeat/docker/_entrypoint.*.sh

ENTRYPOINT ["/app/cmd/beats/scriptablebeat/docker/_entrypoint.run.sh"]
