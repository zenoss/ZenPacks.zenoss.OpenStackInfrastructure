#! /bin/bash 

# First lets create a small flavor

# Flavor "dot" uses no disk space flavor_dot_id is templated.
nova flavor-create --is-public true m1.dot ${flavor_id_dot} 128 0 1 --rxtx-factor .1


# Create an instance with nova: After Network Definition
nova boot apple  --image cirros --flavor ${flavor_id_dot}
nova boot banana --image cirros --flavor ${flavor_id_dot}
nova boot cherry --image cirros --flavor ${flavor_id_dot}


