#!/bin/bash

# -----------------------------------------------------------------------------
# Setup basic local controller host.
# -----------------------------------------------------------------------------

function install_yum_packages()
{
   declare -a packages=("${!1}")

   for pkg in ${packages[@]} ; do

      rpm -q $pkg &> /dev/null
      pkg_status=$?

      if [ $pkg_status -gt 0 ]; then
         echo -e "\e[1;31m $pkg is not installed: Installing now... \e[0m"
         sudo yum install -yq $pkg
      else
         echo -e "\e[1;32m $pkg installed. moving on... \e[0m"
      fi
   done
}

function install_apt_packages()
{
   declare -a packages=("${!1}")

   for pkg in ${packages[@]} ; do

      dpkg -s $pkg &> /dev/null
      pkg_status=$?

      if [ $pkg_status -gt 0 ]; then
         echo -e "\e[1;31m $pkg is not installed: Installing now... \e[0m"
         sudo apt-get install -y $pkg
      else
         echo -e "\e[1;32m $pkg installed. moving on... \e[0m"
      fi
   done
}

prereq_packages_cos7=(
epel-release
ansible
sshpass
)

prereq_packages_deb=(
ansible
)

# -----------------------------------------------------------------------------
# Verify and Install needed packages for getting things going on local host
# -----------------------------------------------------------------------------


echo "Installing Required prereq Packages on your Server"

distro=$(grep -shE "^ID=" /etc/os-release | sed 's/ID=//g;s/"//g')
echo Linux Distribution = $distro

case $distro in

   redhat|centos)
      deploy_host_version=$(rpm -qa \*-release | grep -ei "redhat|centos" | cut -d"-" -f3)
      if [ $deploy_host_version -ne 7 ]; then
         echo wrong version of redhat/centos \; must use centos or redhat 7
         exit 0
      else
         echo Installing Centos/RHEL Control System
      fi
      install_yum_packages prereq_packages_cos7[@]
      ;;

   debian)

      echo -e "\e[1;31m Installing Debian Control system \e[0m"
      install_apt_packages prereq_packages_deb
      ;;

   ubuntu)

      echo Installing on Ubuntu Control system
      sudo apt-get install -y software-properties-common
      sudo apt-add-repository ppa:ansible/ansible
      sudo apt-get update
      sudo apt-get install -y ansible
      ;;

   *)
      echo Distro not found. Abandon ship!
      exit 1

esac


# -----------------------------------------------------------------------------
# Display documentation
# -----------------------------------------------------------------------------

echo -e "\e[1;31m Be sure to edit config files referenced in README.rst \e[0m"
echo
echo -e "\e[1;32m Please Hit <return> to continue or ctrl-c to stop"
echo -e "\e[0m"
read answer
