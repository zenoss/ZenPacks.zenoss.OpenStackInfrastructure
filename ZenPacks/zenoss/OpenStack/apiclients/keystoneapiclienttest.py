from keystoneapiclient import KeystoneAPIClient

username = 'admin'
password = 'password'
project_id = 'demo'
url = 'http://192.168.56.104:5000/v2.0'

kac = KeystoneAPIClient(url, username, password, project_id)

# import pdb; pdb.set_trace()
#print ""
print 'token result:',  kac.get_token().result
print ""
print 'endpoints: ', kac.get_endpoints().result
print ""
print 'roles: %s' % kac.get_roles().result
print ""
print 'service: %s' % kac.get_services().result
print ""
print 'tenants: %s' % kac.get_tenants().result
print ""
print 'user: %s' % kac.get_users().result
print ""
print 'regions: %s' % kac.get_regions().result
print ""
print 'ceilo: %s' % kac.get_ceilometerurl('RegionOne').result
