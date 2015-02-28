#!/bin/python

# script to telnet with expect

import pexpect


_cmd = 'telnet rtr-farm19 23'
session = pexpect.spawn( _cmd )

responses = [ \
  '(?i)password:', #0 \
  '(?!)username:', #1 \
#  "((?i)Connection refused|\%Bad password)", #2 \
#  "(?i)connection closed by (remote|foreign) host", #3 \
#  "(?i)Name or service not known", #4 \
#  "(?i)no route to host", #5 \
  pexpect.TIMEOUT, #6 \
]

i = session.expect( responses )

print i



