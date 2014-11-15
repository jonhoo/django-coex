This project aims to build a concolic execution checker for Django web
applications. Concolic execution can be used to verify that certain invariants
hold for a system (such as money never leaving a bank unless a transaction is
recorded) without incurring the cost of full-blown symbolic checking.

Initially, the goal is to get the checker to work for the Django version of the
Zoobar demo application hosted here: https://github.com/jonhoo/django-zoobar.
Although we want to try to avoid changes to Django to accomplish this, we
maintain a separate fork at https://github.com/jonhoo/django-concolic,
currently based off 1.7 stable, which may include modifications that are
necessary to get concolic execution to work properly.

The code is based on the concolic execution framework built for [Lab
3](http://css.csail.mit.edu/6.858/2014/labs/lab3.html) in MIT's class 6.858
Computer Security, Fall 2014.
