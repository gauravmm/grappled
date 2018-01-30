#!/bin/bash

set -e

if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root."
  exit
fi

# Install prerequisites
apt install python3 python3-pip

# Make sure global pip is at the latest version
pip3 install --upgrade pip 

# Install the module
pip3 install git+git://github.com/gauravmm/grappled.git

# Create the user and group
useradd -r grappled

# Make global config directory:
mkdir -p /etc/grappled.d/
chgrp grappled /etc/grappled.d/
chmod 0755 /etc/grappled.d/

# Install the service
cp grappled.service /lib/systemd/system/
chown grappled:grappled /lib/systemd/system/grappled.service
chmod 0755 /lib/systemd/system/grappled.service

systemctl enable grappled.service
# It will fail until a new config file is added.
systemctl start grappled.service

# TODO: Add sudo authority to allow grappled to become another user.
# echo "grappled  ALL=(cooking) NOPASSWD:ALL" > /etc/sudoers.d/10-grappled-cooking