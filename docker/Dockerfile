# A Ubuntu based Docker image with the following installed:
# - Python 3
# - pip3
# - curl
# - zip and unzip

FROM ubuntu:latest

# Update oneself
RUN apt-get update && apt-get install -y

# Install Python 3
RUN apt-get install -y python3 python3-pip
# Upgrade pip
RUN pip3 install --upgrade pip

# Install curl
RUN apt-get install -y curl

# Install zip and unzip
RUN apt-get install -y zip unzip

WORKDIR /root

COPY . .

# Wait forever // TODO: Remove this
CMD ["tail", "-f", "/dev/null"]
