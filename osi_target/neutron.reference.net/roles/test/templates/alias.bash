nova_services="
{% for svc in nova_services %}
{{svc}}
{% endfor %}
"
restart_nova()
{
   for svc in $nova_services; do
      sudo service "$svc" restart;
   done
}

# Define Neutron services to bounce
neutron_services="
{% for svc in neutron_services %}
{{svc}}
{% endfor %}
"
restart_neutron()
{
   for svc in $neutron_services; do
      sudo service "$svc" restart;
   done
}

ceilometer_services="
{% for svc in ceilometer_services %}
{{svc}}
{% endfor %}
"
restart_ceilometer()
{
   for svc in $ceilometer_services; do
      sudo service "$svc" restart;
   done
}

# Now: bounce most of nova/neutron to pick up those config file changes
# echo "Bouncing Nova Services"
# for svc in ${nova_services[@]} ; do
#    service "$svc" restart;
# done

res()
{
   echo "Restarting $1 Services"
   if [ -z "$1" ]; then
      echo You must provide a service name
      name=${0##*/}
      echo "Usage: $name SERVICENAME [SERVICENAME ...]"
      return 1
   fi

   local name=$1

   case "$name" in

      nova)

         restart_nova
         ;;

      neutron|neu)

         restart_neutron
         ;;

      ceilometer|ceil|cei)

         restart_ceilometer
         ;;

      *)
         echo "I don't see the $name service"
         ;;

   esac
}
