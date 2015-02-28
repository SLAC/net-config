import argparse

from slac_utils.command import Command, CommandDispatcher
from slac_utils.logger import init_loggers
from slac_utils.util import get_array
from slac_utils.string import underscore_to_camelcase, camel_case_to_underscore

from slac_utils.klasses import path_of_module, import_module, inheritors, create_klass

from netconfig.backup.configuration import Configuration, all_config_klasses

import sys
import os
import logging


class Sanitise( Command ):
    """
    Redacts passwords on configuration files
    """
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( 'files', help="config files to scrub", nargs="+" )
        parser.add_argument( '--replace', help="overwrite the config file", default=False, action='store_true' )
        
        
    def run( self, *args, **kwargs ):
        init_loggers( **kwargs )

        # find out all known redact matches required
        scrubs = []
        for m in all_config_klasses():
            k = underscore_to_camelcase(m)
            c = 'netconfig.backup.configuration.%s' % camel_case_to_underscore(k)
            try:
                d = import_module( c, k )
                f = '%s.%s' % (c,k)
                s = create_klass(f).scrub_matches
                # logging.debug("> %s: %s" % (f,s))
                for i in s:
                    scrubs.append( i )
            except:
                pass            
        # logging.error("scrubs: %s" % scrubs)

        for f in kwargs['files']:
            logging.info("processing %s" % (f,)  )
        
            fn = open( f, 'r' )
            this = []
            for l in fn.readlines():
                this.append( l.rstrip() )
                    
            conf = Configuration( this )
            conf.scrub_matches = scrubs

            if 'replace' in kwargs and kwargs['replace']:
                with open( f, 'w' ) as fh:
                    for i in conf.scrub( this ):
                        fh.write( i + "\n")
            else:
                for i in conf.scrub( this ):
                    print i
            

class Configs( CommandDispatcher ):
    """
    Configuration Tools
    """
    commands = [ Sanitise, ]
