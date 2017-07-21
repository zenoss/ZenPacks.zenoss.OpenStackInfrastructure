###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2017, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################


class APIClientError(Exception):
    """Parent class of all exceptions raised by api clients."""
    pass


class BadRequestError(APIClientError):
    """Wrapper for HTTP 400 Bad Request error."""
    pass


class UnauthorizedError(APIClientError):
    """Wrapper for HTTP 401 Unauthorized error."""
    pass


class NotFoundError(APIClientError):
    """Wrapper for HTTP 400 Bad Request error."""
    pass


class NotSupported(APIClientError):
    """Client tried to call an API method that is not supported by the client"""
    pass
