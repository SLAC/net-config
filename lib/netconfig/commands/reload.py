import argparse

from slac_utils.command import Command
from slac_utils.logger import init_loggers
from slac_utils.util import get_array

from netconfig import NewNetConfig as NetConfig
from netconfig.recipes.system import reload_and_monitor

import sys
import logging

class Reload( Command ):
    """
    Logs on to device(s) and updates the firmware to the defined version(s)
    """
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( '-f', '--profile', help='profile to use', default=None )
        parser.add_argument( 'device', help='device name', nargs="+" )
        parser.add_argument( '-w', '--wait', help='number of seconds to wait for device to comeback online', default=900 )
        parser.add_argument( '-d', '--delay', help='probe interval in seconds', default=30 )
        
    def run( self, *args, **kwargs ):
        
        init_loggers( **kwargs )
        
        options = {}
        for i in ( 'profile', ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]
        netconfig = NetConfig( kwargs['config'] )        

        for d in get_array( kwargs['device'] ):

            try:
                # get device
                device = netconfig.get( d, options=options )
                netconfig.connect( device, **options )        

                # reload device and make sure it comes back!
                msg_per_loop = '.'
                for e in reload_and_monitor( netconfig, device, options=options, wait=int(kwargs['wait']), delay=int(kwargs['delay']), message_per_loop=msg_per_loop ):
                    if isinstance(e,str):
                        if e == msg_per_loop:
                            print "%s" % (e,),
                        else:
                            print "%s" % (e,)
                    else:
                        print
                        device = e

                logging.info("%s" % (device.system.get(),) )
                
            except Exception,e:
                logging.error("%s: %s" % (type(e),e))
                
            
                