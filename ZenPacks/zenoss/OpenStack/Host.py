##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from . import schema

class Host(schema.Host):

	# These will be derived from the services present on the host
	def isComputeNode(self):
		pass

	def isControllerNode(self):
		pass