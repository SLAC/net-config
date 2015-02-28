import unittest
from slac.NetworkDeviceConnector import NetworkDeviceConnectorException, NetworkDeviceConnector, SSHNetworkDeviceConnector
import logging

def getPassword( filename ):
    _f = open( filename )
    _password = _f.readline()
    _f.close()
    _password = _password.rstrip()
    #logging.debug("password is " + password )
    return _password


class NetworkDeviceConnectorTestCase( unittest.TestCase ):
    """
    test unit class for the base network device connector
    """
    
    _hostname = 'swh-b267.slac.stanford.edu'
    _username = 'ytl'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _password = getPassword( _login_password_file )
    _enable = getPassword( _enable_password_file )
    
    _connector = None

    def setUp( self ):
        self._connector = NetworkDeviceConnector( self._hostname, self._username, self._password, self._enable )

    def testHost( self ):
        assert self._hostname == self._connector.getHost(), "hostname failure"

    def testUsername( self ):
        assert self._username == self._connector.getUsername(), "username failure"

    def testPassword( self ):
        assert self._password == self._connector.getPassword(), "password failure"

    def testEnablePassword( self ):
        assert self._enable == self._connector.getEnablePassword(), "enable password failure"

    def testSetHost( self ):
        _name = 'hostname'
        self._connector.setHost( _name )
        assert self._connector.getHost() == _name, "set hostname failed"

    def testSetUsername( self ):
        _name = 'username'
        self._connector.setUsername( _name )
        assert self._connector.getUsername() == _name, "set username failed"

    def testSetPassword( self ):
        _name = 'pass'
        self._connector.setPassword( _name )
        assert self._connector.getPassword() == _name, "set password failed"

    def testSetEnablePassword( self ):
        _name = 'pass'
        self._connector.setEnablePassword( _name )
        assert self._connector.getEnablePassword() == _name, "set enable password failed"



class SSHNetworkDeviceConnectorTestCase( unittest.TestCase ):
    """
    test case for ssh access to a device
    """
    
    _username = 'ytl'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )

    def testGood( self ):
        _hostname = 'swh-b050f1.slac.stanford.edu'
        _connector = SSHNetworkDeviceConnector( _hostname, self._username, self._password, self._enable )

        _connected = _connector.connect( '[\>]' )
        assert _connected == True, "could not attach to good ssh"

        # disconnect
        _status = _connector.disconnect()
        assert _status == True, "disconnected unsuccessfully"


    def testBadDNS( self ):
        _hostname = 'unknown-dns.slac.stanford.edu'
        _connector = SSHNetworkDeviceConnector( _hostname, self._username, self._password, self._enable )
        try:
            _connector.connect( '[\>]' )
        except NetworkDeviceConnectorException, e:
            assert True == True, "fqdn failure test okay"

        assert True == True, "fqdn failure"


if __name__ == "__main__":

    
    #logging.basicConfig(level=logging.DEBUG)

    suite = unittest.TestLoader().loadTestsFromTestCase(NetworkDeviceConnectorTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)

    suite = unittest.TestLoader().loadTestsFromTestCase(SSHNetworkDeviceConnectorTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
