#!/bin/sh
# Run as root only inside the separate ArcheonSim WSL distribution.
set -eu
test "$(id -u)" = 0
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-dev gfortran gcc g++ make libopenmpi-dev openmpi-bin libnetcdf-dev libnetcdff-dev libfftw3-dev pkg-config
if ! id archeon >/dev/null 2>&1; then useradd --create-home --shell /bin/bash archeon; fi
if [ ! -d /opt/archeon-venv ]; then python3 -m venv /opt/archeon-venv; fi
/opt/archeon-venv/bin/python -m pip install --upgrade pip
/opt/archeon-venv/bin/python -m pip install 'numpy==1.26.4' 'scipy==1.13.1' 'exoplasim==3.4.2' meson ninja netCDF4
chown -R archeon:archeon /opt/archeon-venv
runuser -u archeon -- /opt/archeon-venv/bin/python -c 'import exoplasim; import importlib.metadata; print(importlib.metadata.version("exoplasim"))'
