#!/usr/bin/env python2

verbose = True

import os
import symex.fuzzy as fuzzy
import __builtin__
import inspect
import symex.importwrapper as importwrapper
import symex.rewriter as rewriter

importwrapper.rewrite_imports(rewriter.rewriter)

from symex.symdjango import SymDjango
import symex.symsql
import symex.symeval

app = "zoobar"
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

def startresp(status, headers):
  if verbose:
    print('startresp', status, headers)

d = SymDjango(app, os.path.abspath(os.path.dirname(__file__) + '/app'), appviews)

# Only safe to load now that it's been patched and added to import path
import zoobar

def report_balance_mismatch():
  print("WARNING: Balance mismatch detected")

def report_zoobar_theft():
  print("WARNING: Zoobar theft detected")

def adduser(username):
  from django.contrib.auth.models import User
  u = User.objects.create_user(username, '', 'password')
  u.save()

def test_stuff():
  req = d.new(startresp)

  from django.contrib.auth.models import User
  User.objects.all().delete()
  adduser('alice')
  adduser('bob')
  balance1 = sum([u.person.zoobars for u in User.objects.all()])

  from zapp.models import Transfer
  Transfer.objects.all().delete()

  ## In two cases, we over-restrict the inputs in order to reduce the
  ## number of paths that "make check" explores, so that it finishes
  ## in a reasonable amount of time.  You could pass unconstrained
  ## concolic values for both REQUEST_METHOD and PATH_INFO, but then
  ## zoobar generates around 2000 distinct paths, and that takes many
  ## minutes to check.
  path = '/trans' + fuzzy.mk_str('path')
  if path.startswith('//'):
    ## Don't bother trying to construct paths with lots of slashes;
    ## otherwise, the lstrip() code generates lots of paths..
    return

  resp = req.get(path
      , HTTP_COOKIE  = fuzzy.mk_str('cookie') # this probably won't work for Django
      , HTTP_REFERER = fuzzy.mk_str('referrer') # why is this fuzzed?
      )

  if verbose:
    for x in resp:
      print(x)

  ## Exercise 6: your code here.

  ## Detect balance mismatch.
  ## When detected, call report_balance_mismatch()

  ## Detect zoobar theft.
  ## When detected, call report_zoobar_theft()

fuzzy.concolic_test(test_stuff, maxiter=2000, verbose=1)
