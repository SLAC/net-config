""" unittest for ssh network device """

from netconfig import NetConfig
from netconfig.Device import *

import unittest
import logging


class WrapperTestCase( unittest.TestCase ):

    args = {
        '-h'    : 'help',
        '--help': 'help',
        '-u'    : 'username=',
        '--username'    : 'username=',
        '-p'    : 'password=',
        '--password': 'password=',
        '-P'    : 'enable_password=',
        '--enable_password'    : 'enable_password=',
        '-t'    : 'type=',
        '--type'    : 'type=',
        '-e'    : 'enable',
        '--enable': 'enable',
        '-v'    : 'verbose',
        '--verbose' : 'verbose'
    }
    
    conf_file = '/afs/slac.stanford.edu/g/scs/net/projects/net-config/etc/net-config/net-config.conf'
    
    
    def _testParseArgs( self ):
        getopt_short, getopt_long = slac.netconfig._parseArgs( self.args )
        #logging.warn( "short " + getopt_short )
        assert getopt_short == 'ehu:t:vp:P:', "could not match short opts"
        logging.warn( "long " + str(getopt_long) )
        assert True == True, "found connector type"

    def testInit(self):
        nc = NetConfig( self.conf_file )
        assert type(nc) == NetConfig, 'initiation failed'
        
    # def testSystemConfig( self ):
    #     file_path = '/afs/slac.stanford.edu/g/scs/net/projects/net-config/etc/net-config/netconfig.conf'
    #     config = NetConfig( file_path )
    #     assert config.get( 'net-config', 'profiles_file' ) == '/afs/slac.stanford.edu/g/scs/net/projects/net-config/config/profiles', "coudl not get system config"
    # 
    def _testGetNetworkDevice1( self ):
        nc = NetConfig( self.conf_file )
        swh = nc.get( 'swh-b050f1' )
        assert type(swh) == CiscoIOSSwitch, 'could not get a device ' + str(type(swh))
        assert swh.connect() == True, 'could not connect to device'
        res = swh.disconnect()
        assert res == None, 'could not disconnect to device ' + str(res)
        

    def testForceProbe( self ):
        nc = NetConfig( self.conf_file )
        swh = nc.get( 'swh-b050f1', options={ 'profile': 'auto' } )
        assert type(swh) == CiscoIOSSwitch, 'could not get a device ' + str(type(swh))

if __name__ == "__main__":
    
    logging.basicConfig(level=logging.DEBUG)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(WrapperTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)