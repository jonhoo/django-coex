#!/usr/bin/env python

import os
from symex import symdjango

# name of app being mocked
app = "zoobar"

# route matches module.view if [module][view] lambda returns true
appviews = {
        "zapp": {
            "index": (lambda p: p == "/")
        },
        "zlogio": {
            "login": (lambda p: p == "/accounts/login/"),
            "logout": (lambda p: p == "/accounts/logout/"),
        },
        "": {}
}

def start_response(status, response_headers):
    print("\n%18s: %s" % ("RESULT", status))
    print("%18s: %s" % ("------", "--------------"))
    for h, v in response_headers:
        print("%18s: %s" % (h, v))
    print("")

d = symdjango.SymDjango(app, os.path.abspath(os.path.dirname(__file__) + '/app'), appviews)
f = open('result.html', 'wb')
req = d.new(start_response)
body = req.get('/accounts/login/')
for c in body:
    f.write(c)
body.close()
f.close()
