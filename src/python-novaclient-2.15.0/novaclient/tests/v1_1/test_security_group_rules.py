from novaclient import exceptions
from novaclient.v1_1 import security_group_rules
from novaclient.tests import utils
from novaclient.tests.v1_1 import fakes


cs = fakes.FakeClient()


class SecurityGroupRulesTest(utils.TestCase):
    def test_delete_security_group_rule(self):
        cs.security_group_rules.delete(1)
        cs.assert_called('DELETE', '/os-security-group-rules/1')

    def test_create_security_group_rule(self):
        sg = cs.security_group_rules.create(1, "tcp", 1, 65535, "10.0.0.0/16")

        body = {
            "security_group_rule": {
                "ip_protocol": "tcp",
                "from_port": 1,
                "to_port": 65535,
                "cidr": "10.0.0.0/16",
                "group_id": None,
                "parent_group_id": 1,
            }
        }

        cs.assert_called('POST', '/os-security-group-rules', body)
        self.assertTrue(isinstance(sg, security_group_rules.SecurityGroupRule))

    def test_create_security_group_group_rule(self):
        sg = cs.security_group_rules.create(1, "tcp", 1, 65535, "10.0.0.0/16",
                                            101)

        body = {
            "security_group_rule": {
                "ip_protocol": "tcp",
                "from_port": 1,
                "to_port": 65535,
                "cidr": "10.0.0.0/16",
                "group_id": 101,
                "parent_group_id": 1,
            }
        }

        cs.assert_called('POST', '/os-security-group-rules', body)
        self.assertTrue(isinstance(sg, security_group_rules.SecurityGroupRule))

    def test_invalid_parameters_create(self):
        self.assertRaises(exceptions.CommandError,
            cs.security_group_rules.create,
            1, "invalid_ip_protocol", 1, 65535, "10.0.0.0/16", 101)
        self.assertRaises(exceptions.CommandError,
            cs.security_group_rules.create,
            1, "tcp", "invalid_from_port", 65535, "10.0.0.0/16", 101)
        self.assertRaises(exceptions.CommandError,
            cs.security_group_rules.create,
            1, "tcp", 1, "invalid_to_port", "10.0.0.0/16", 101)

    def test_security_group_rule_str(self):
        sg = cs.security_group_rules.create(1, "tcp", 1, 65535, "10.0.0.0/16")
        self.assertEqual('1', str(sg))

    def test_security_group_rule_del(self):
        sg = cs.security_group_rules.create(1, "tcp", 1, 65535, "10.0.0.0/16")
        sg.delete()
        cs.assert_called('DELETE', '/os-security-group-rules/1')
