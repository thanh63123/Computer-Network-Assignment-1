#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

from urllib.parse import urlparse

def get_auth_from_url(url):
    """
    Given a url with authentication components, extract them into a tuple of
    username,password.
    
    :rtype: (str,str)
    """
    if not url:
        return ("", "")

    parsed = urlparse(url)

    username = parsed.username if parsed.username else ""
    password = parsed.password if parsed.password else ""

    return (username, password)
