#!/bin/env python
import logging
from netconfig import NewNetConfig as NetConfig

logging.basicConfig( level=logging.DEBUG )

nc = NetConfig( '/u/sf/ytl/net/projects/net-config/conf/net-config.yaml')
ap = nc.get( 'AP-280R112' )
ap.connect()

print ap.prompt.request( 'del config.txt ', interact={ 'confirm': '\n', 'question': '\n' } )