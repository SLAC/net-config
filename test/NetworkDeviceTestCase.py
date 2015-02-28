""" unittest for ssh network device """

from slac.NetworkDevice import NetworkDeviceException, NetworkDevice, CiscoIOSNetworkDevice, CiscoCATOSNetworkDevice, CiscoTopSpinOSNetworkDevice
import unittest
import logging
from types import *

def getPassword( filename ):
    _f = open( filename )
    _password = _f.readline()
    _f.close()
    _password = _password.rstrip()
    #logging.debug("password is " + password )
    return _password


class NetworkDeviceTestCase( unittest.TestCase ):

    _hostname = 'swh-b267.slac.stanford.edu'
    _connector_type = 'ssh'
    _username = 'ytl'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )
    
    def testBadConnectorType( self ):
        connector_type = 'nothing'
        device = None
        try:
            device = NetworkDevice( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        except NetworkDeviceException, e:
            assert True == True, "found connector type"

    def testConnect( self ):
        device = NetworkDevice( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert device.connect() == True, "could not connect to device"



class CiscoIOSNetworkDeviceTestCase( unittest.TestCase ):

    _hostname = 'swh-b267.slac.stanford.edu'
    _connector_type = 'ssh'
    _username = 'ytl'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )

    def testConnect( self ):
        device = CiscoIOSNetworkDevice( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert device.connect() == True, 'could not connect to ' + self._hostname
        assert device.enableMode() == True, 'could enter enable mode'
        output = device.getRunningConfiguration()
        #logging.debug( output )
        assert type( output ) == StringType, 'could not get running configuration'
        

class CiscoCATOSNetworkDeviceTestCase( unittest.TestCase ):

    _hostname = 'swh-core1old.slac.stanford.edu'
    _connector_type = 'ssh'
    _username = 'ytl'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )

    def testConnect( self ):
        device = CiscoCATOSNetworkDevice( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert device.connect() == True, 'could not connect to ' + self._hostname
        assert device.enableMode() == True, 'could enter enable mode'
        output = device.getRunningConfiguration()
        logging.debug( output )
        assert type( output ) == StringType, 'could not get running configuration'


class CiscoTopSpinOSNetworkDeviceTestCase( unittest.TestCase ):

    _hostname = 'swh-ibfarmcore1.slac.stanford.edu'
    _connector_type = 'ssh'
    _username = 'super'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )

    def testConnect( self ):
        device = CiscoTopSpinOSNetworkDevice( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert device.connect() == True, 'could not connect to ' + self._hostname
        assert device.enableMode() == True, 'could enter enable mode'
        output = device.getRunningConfiguration()
        logging.debug( output )
        assert type( output ) == StringType, 'could not get running configuration'

        

if __name__ == "__main__":
    
    #logging.basicConfig(level=logging.DEBUG)

    suite = unittest.TestLoader().loadTestsFromTestCase(NetworkDeviceTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(CiscoIOSNetworkDeviceTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(CiscoCATOSNetworkDeviceTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(CiscoTopSpinOSNetworkDeviceTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)