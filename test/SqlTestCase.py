""" unittest for database access """

import slac.netconfig
import unittest
import logging
from types import *


def parseArgs():
        """
        parses the system arguments to a consistent argument set
        """
        options = {
        'help': 0,
        'verbose': 0,
        'path': None
        }
        try:
                opts = getopt.getopt( sys.argv[1:], "hv:", ['help', 'verbose'])
                for o, a in opts:
                        if o in ( '-h', '--help' ):
                                options['help'] = 1
                        elif o in ( '-v', '--verbose' ):
                                options['verbose'] = 1
                        else:
                                assert False, "unhandled option " + str(o)

        except getopt.GetoptError, e:
                print str(e)
                sys.exit(2)


