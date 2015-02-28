#!/usr/bin/env python

import logging
import getopt
import sys
import os

from netconfig import NetConfig, util, config_file

from netconfig.Configuration import *


def usage():
    print "Santitises a configuration file"
    print "Usage: "
    print "  net-config sanitise_config [--verbose|-v] FILE1 [FILE2...]"
    print ""
    print "options are:"
    print "  --replace|-r            overwrite file"
    print "  --verbose|-v            verbosely reports on what's happening"

if __name__ == "__main__":
    
    config_file = config_file()
    args = {
        '-h'        : 'help',
        '--help'    : 'help',

        '-r'        : 'replace',
        '--replace'    : 'replace',
        
        '-v'        : 'verbose',
        '--verbose' : 'verbose'

    }

    def append_scrubs( orig, klass ):
        for i in klass.scrub_matches:
            orig.scrub_matches.append( i )
        # logging.error("I: %s" % (orig.scrub_matches,))
        return orig
    
    #logging.basicConfig(level=logging.DEBUG)
    
    # parse arguments
    files, options = util.parseArgs( args )

    if (options.has_key( 'help' ) and options['help'] == 1) or len(files) < 1:
        usage()
        sys.exit( )

    # inheritors of backup configuration
    logging.error( '%s' % inheritors( 'netconfig.backup.configuration' )

    sys.exit(1)
    for f in files:
        # logging.info("FILE %s" % (f,)  )

        fn = open( f, 'r' )
        this = []
        for l in fn.readlines():
            this.append( l.rstrip() )
        
        conf = Configuration( this )
        
        conf = append_scrubs( conf, CiscoIOSConfiguration() )
        conf = append_scrubs( conf, CiscoIOSWirelessConfiguration() )
        conf = append_scrubs( conf, CiscoASAConfiguration() )
        conf = append_scrubs( conf, CiscoCATOSConfiguration() )
        conf = append_scrubs( conf, CiscoNexusConfiguration() )
        conf = append_scrubs( conf, CiscoTopSpinConfiguration() )
        conf = append_scrubs( conf, CiscoASAConfiguration() )
        conf = append_scrubs( conf, AristaConfiguration() )
        conf = append_scrubs( conf, BigIPLTMConfiguration() )
        
        if 'replace' in options and options['replace']:
            with open( f, 'w' ) as fh:
                for i in conf.scrub( this ):
                    fh.write( i + "\n")
        else:
            for i in conf.scrub( this ):
                print i
        