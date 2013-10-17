# Copyright (c) 2011 X.commerce, a business unit of eBay Inc.
# Copyright 2011 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from novaclient import base


class FloatingIP(base.Resource):
    def delete(self):
        """
        Delete this floating ip
        """
        self.manager.delete(self)


class FloatingIPManager(base.ManagerWithFind):
    resource_class = FloatingIP

    def list(self):
        """
        List floating ips for a tenant
        """
        return self._list("/os-floating-ips", "floating_ips")

    def create(self, pool=None):
        """
        Create (allocate) a  floating ip for a tenant
        """
        return self._create("/os-floating-ips", {'pool': pool}, "floating_ip")

    def delete(self, floating_ip):
        """
        Delete (deallocate) a  floating ip for a tenant

        :param key: The :class:`Keypair` (or its ID) to delete.
        """
        self._delete("/os-floating-ips/%s" % base.getid(floating_ip))

    def get(self, floating_ip):
        """
        Retrieve a floating ip
        """
        return self._get("/os-floating-ips/%s" % base.getid(floating_ip),
                         "floating_ip")
