from keystoneapiclient import KeystoneAPIClient

username = 'admin'
password = 'password'
project_id = 'demo'
url = 'http://192.168.56.104:5000/v2.0'

kac = KeystoneAPIClient(url, username, password, project_id)
hdr = {}
hdr['X-Auth-Token'] = None
hdr['Content-Type'] = 'application/json'
body = {}
body['allow_redirects'] = True
body['auth'] = {}
body['auth']['tenantName'] = 'demo'
body['auth']['passwordCredentials'] = {}
body['auth']['passwordCredentials']['username'] = 'admin'
body['auth']['passwordCredentials']['password'] = 'password'

def getdata(self, data):
    print data
    return data

def errdata(self, failure):
    print ('%s: %s', 'OpenStackCeilometerError', failure.getErrorMessage())
    return failure.getErrorMessage()

# import pdb; pdb.set_trace()
print ""
print  kac.get_token().result
print ""
print kac.get_endpoints().result
print ""
print kac.get_roles().result
print ""
print kac.get_services().result
print ""
print kac.get_tenants().result
print ""
print kac.get_users().result
print ""
print kac.get_regions().result
print ""
print kac.get_meters().result
