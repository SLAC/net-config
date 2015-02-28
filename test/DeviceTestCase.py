""" unittest for ssh network device """

from netconfig.Device import *
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


class DeviceTestCase( unittest.TestCase ):

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
            device = Device( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        except DeviceException, e:
            assert True == True, "found connector type"

    def testConnect( self ):
        swh = Device( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert swh.connect() == True, "could not connect to device"
        l = 0
        for i in swh.prompt.tell( 'show version | inc Cisco' ):
            l = l +1
        assert l == 4, 'tell returned funny number of lines'

        # string return
        l = swh.prompt.request( 'show version | inc cryptographic features' )
        assert l == 'This product contains cryptographic features and is subject to United', 'single line response wrong: ' + str(l)

        # many lines
        l = swh.prompt.request( 'show version | inc cryptographic' )
        # logging.error("L: " + str(l))
        assert l == '''This product contains cryptographic features and is subject to United
use. Delivery of Cisco cryptographic products does not imply
A summary of U.S. laws governing Cisco cryptographic products may be found at:''', 'multiline request output'

        # true/false
        assert swh.prompt.ask( 'show ip') == False, 'error command failed'
        assert swh.prompt.ask( 'show int status | inc Gi') == True, 'good command failed'

        swh.disconnect()


class CiscoIOSSwitchTestCase( unittest.TestCase ):

    _hostname = 'swh-b267.slac.stanford.edu'
    _connector_type = 'ssh'
    _username = 'ytl'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )

    def setUp( self ):
        self.device = CiscoIOSSwitch( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        try:
            assert self.device.connect() == True, 'could not connect to ' + self._hostname
        except:
            assert True == False, 'could not connect to device'
            
    def teardDown( self ):
        assert self.device.disconnect() == True, 'could not disconnect'

    def testSystemConfig( self ):
        output = self.device.system.config.get()
        #logging.debug( output )
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
        # logging.debug(str(output))
    
    def _testSystemModel(self):
        # assert device.enableMode() == True, 'could enter enable mode'
        assert self.device.system.model.get() == ['WS-C3750-48TS', 'WS-C3750-24TS'], 'models do not match'
        assert self.device.system.firmware.version() == ['12.2(44)SE1', '12.2(44)SE1'], 'fw do not match'

    def _testVlan(self):
        assert len(self.device.layer2.vlan.get().keys()) > 0, 'not vlans found'

    def _testPorts(self):
        self.device.prompt.terminal_buffer( 0 )
        # all ports
        for p in self.device.ports:
            logging.debug("found port: " + str(p))
            assert type(p) == Port, 'not a port returned'
        
    def _testState(self):
        # change a port
        logging.debug("set state")
        p = Port()
        p['port'] = 'Gi2/0/2'
        p['state'] = False
        # turn it off for initial test
        res = self.device.ports.set( p )
        # turn it on
        p['state'] = True
        assert self.device.ports.set( p ) == True, 'did not turn on port'
        # so action required, ie try enabling it again
        assert self.device.ports.set( p ) == None, 'did not do nothing!'
        # turn it off
        p['state'] = False
        assert self.device.ports.set( p ) == True, 'did not turn off'
        
    def _testAlias(self):
        # set alias
        logging.debug("set alias")
        p = Port()
        p['port'] = 'Gi2/0/2'
        p['alias'] = None
        res = self.device.ports.set( p )
        p['alias'] = 'testing'
        assert self.device.ports.set( p ) == True, 'could not set alias'
        p['alias'] = None
        assert self.device.ports.set( p ) == True, 'could unset alias'
        
    def _testTypeAccess(self):
        # set access vlan
        logging.debug("set access vlan")
        p = Port()
        p['port'] = 'Gi2/0/2'
        p['type'] = 'access'
        p['vlan'] = [ 1 ]
        res = self.device.ports.set( p )
        p['vlan'] = [ 300 ]
        assert self.device.ports.set( p ) == True, 'could not set vlan'
        p['vlan'] = None
        assert self.device.ports.set( p ) == True, 'could not set vlan'


class CiscoIOSWirelessTestCase( unittest.TestCase ):

    _hostname = 'ap-cgb375.slac.stanford.edu'
    _connector_type = 'ssh'
    _username = 'netdev'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password.wireless'
    _password = getPassword( _login_password_file )
    # _enable_password_file = ''
    # _enable = getPassword( _enable_password_file )
    _enable = None

    def testSystemConfig( self ):
        device = CiscoIOSWireless( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert device.connect() == True, 'could not connect to ' + self._hostname
        # assert device.enableMode() == True, 'could enter enable mode'
        output = device.system.config.get()
        #logging.debug( output )
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
        # logging.debug(str(output))
        # 
    def testSystemModel(self):
        device = CiscoIOSWireless( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert device.connect() == True, 'could not connect to ' + self._hostname
        assert device.system.model.get() == ['AIR-AP1131AG-A-K9'], 'models do not match'
        assert device.system.firmware.version() == ['12.3(8)JEA'], 'fw do not match'
    
    
    def testPorts(self):
        device = CiscoIOSWireless( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert device.connect() == True, 'could not connect to ' + self._hostname
        try:
            for i in device.system.ports:
                assert 1 == 0, 'wireless ports have been impelmented?!?!'
        except NotImplementedError, e:
            assert 1 == 1, 'did not throw not implemented'
        except:
            assert 1 == 0, 'did not throw not implemented'
            
# 
# class CiscoCATOSNetworkDeviceTestCase( unittest.TestCase ):
# 
#     _hostname = 'swh-core1old.slac.stanford.edu'
#     _connector_type = 'ssh'
#     _username = 'ytl'
#     _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
#     _password = getPassword( _login_password_file )
#     _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
#     _enable = getPassword( _enable_password_file )
# 
#     def testConnect( self ):
#         device = CiscoCATOSNetworkDevice( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
#         assert device.connect() == True, 'could not connect to ' + self._hostname
#         assert device.enableMode() == True, 'could enter enable mode'
#         output = device.getRunningConfiguration()
#         logging.debug( output )
#         assert type( output ) == StringType, 'could not get running configuration'
# 
# 
# class CiscoTopSpinOSNetworkDeviceTestCase( unittest.TestCase ):
# 
#     _hostname = 'swh-ibfarmcore1.slac.stanford.edu'
#     _connector_type = 'ssh'
#     _username = 'super'
#     _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
#     _password = getPassword( _login_password_file )
#     _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
#     _enable = getPassword( _enable_password_file )
# 
#     def testConnect( self ):
#         device = CiscoTopSpinOSNetworkDevice( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
#         assert device.connect() == True, 'could not connect to ' + self._hostname
#         assert device.enableMode() == True, 'could enter enable mode'
#         output = device.getRunningConfiguration()
#         logging.debug( output )
#         assert type( output ) == StringType, 'could not get running configuration'
# 
#         



class DellSwitchTestCase( unittest.TestCase ):

    _hostname = 'swh-farm02a.slac.stanford.edu'
    _connector_type = 'ssh'
    _username = 'admin'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )


    def setUp( self ):
        self.device = Dell8024( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert self.device.connect() == True, 'could not connect to ' + self._hostname

    def _testSystemConfig( self ):
        output = self.device.system.config.get()
        #logging.debug( output )
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
        # logging.debug(str(output))
    
    def testSystemModel(self):
        # assert device.enableMode() == True, 'could enter enable mode'
        assert self.device.system.model.get() == ['PC8024F'], 'models do not match'
        # assert self.device.system.firmware.version() == ['12.2(44)SE1', '12.2(44)SE1'], 'fw do not match'



class CiscoASATestCase( unittest.TestCase ):

    # _hostname = 'rtr-fwpcdsn1.slac.stanford.edu'
    _hostname = 'rtr-fwvpn1.slac.stanford.edu'

    _connector_type = 'ssh'
    _username = 'sccs'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )


    def setUp( self ):
        self.device = CiscoASA( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert self.device.connect() == True, 'could not connect to ' + self._hostname

    def testSystemConfig( self ):
        output = self.device.system.config.get()
        #logging.debug( output )
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
        # logging.debug(str(output))
    
    def testSystemModel(self):
        assert self.device.system.model.get() == ['ASA5520'], 'models do not match'
        # assert self.device.system.firmware.version() == ['12.2(44)SE1', '12.2(44)SE1'], 'fw do not match'

class CiscoContextASATestCase( unittest.TestCase ):

    # _hostname = 'rtr-fwpcdsn1.slac.stanford.edu'
    _hostname = 'rtr-fwpcdsn1.slac.stanford.edu'

    _connector_type = 'ssh'
    _username = 'sccs'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )


    def setUp( self ):
        self.device = CiscoASA( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert self.device.connect() == True, 'could not connect to ' + self._hostname

    def testSystemConfig( self ):
        output = self.device.system.config.get()
        #logging.debug( output )
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
        # logging.debug(str(output))
    
    def _testSystemModel(self):
        # assert device.enableMode() == True, 'could enter enable mode'
        assert self.device.system.model.get() == ['ASA5520'], 'models do not match'
        # assert self.device.system.firmware.version() == ['12.2(44)SE1', '12.2(44)SE1'], 'fw do not match'


class DigiTestCase( unittest.TestCase ):

    # _hostname = 'rtr-fwpcdsn1.slac.stanford.edu'
    _hostname = 'ts-li19-kly01.slac.stanford.edu'

    _connector_type = 'ssh'
    _username = 'root'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/.mcc/terminal.server.password'
    _password = getPassword( _login_password_file )
    _enable = None

    def setUp( self ):
        self.device = DigiTS( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert type(self.device) == DigiTS, 'incorrect device class'
        assert self.device.connect( empty_prompt=True, timeout=10, options='-o "ProxyCommand ssh mcclogin.slac.stanford.edu /usr/bin/nc -w 1 ts-li19-kly01 22"') == True, 'could not connect to ' + self._hostname

    def testSystemConfig( self ):
        output = self.device.system.config.get()
        #logging.debug( output )
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
        # logging.debug(str(output))



class F5BigPipeTestCase( unittest.TestCase ):

    # _hostname = 'rtr-fwpcdsn1.slac.stanford.edu'
    _hostname = 'rtr-lbserv03-01.slac.stanford.edu'

    _connector_type = 'ssh'
    _username = 'root'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _password = getPassword( _login_password_file )
    _enable = None

    def setUp( self ):
        self.device = F5BigIPBigPipe( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert type(self.device) == F5BigIPBigPipe, 'incorrect device class'
        assert self.device.connect( ) == True, 'could not connect to ' + self._hostname

    def testSystemConfig( self ):
        output = self.device.system.config.get()
        #logging.debug( output )
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
        # logging.debug(str(output))
    
class F5TMSHTestCase( unittest.TestCase ):

    # _hostname = 'rtr-fwpcdsn1.slac.stanford.edu'
    _hostname = 'rtr-lbserv03-01-new.slac.stanford.edu'

    _connector_type = 'ssh'
    _username = 'root'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _password = getPassword( _login_password_file )
    _enable = None

    def setUp( self ):
        self.device = F5BigIPTMSH( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert type(self.device) == F5BigIPTMSH, 'incorrect device class'
        assert self.device.connect( ) == True, 'could not connect to ' + self._hostname

    def testSystemConfig( self ):
        output = self.device.system.config.get()
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
        # logging.debug(str(output))
    
    

class AristaTestCase( unittest.TestCase ):

    _hostname = 'swh-farm01a.slac.stanford.edu'
    _connector_type = 'ssh'
    _username = 'sccs'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'
    _enable = getPassword( _enable_password_file )


    def setUp( self ):
        self.device = Arista7k( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert type(self.device) == Arista7k, 'object not match'
        assert self.device.connect() == True, 'could not connect to ' + self._hostname

    def testSystemConfig( self ):
        output = self.device.system.config.get()
        #logging.debug( output )
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
        # logging.debug(str(output))
    
    def _testSystemModel(self):
        # assert device.enableMode() == True, 'could enter enable mode'
        assert self.device.system.model.get() == ['WS-C3750-48TS', 'WS-C3750-24TS'], 'models do not match'
        assert self.device.system.firmware.version() == ['12.2(44)SE1', '12.2(44)SE1'], 'fw do not match'


class BlueCoatTestCase( unittest.TestCase ):

    _hostname = 'proxysg01.slac.stanford.edu'
    _connector_type = 'ssh'
    _username = 'admin'
    _login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/.bluecoat/login.password'
    _password = getPassword( _login_password_file )
    _enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/.bluecoat/login.password'
    _enable = getPassword( _enable_password_file )
    
    def setUp( self ):
        self.device = BlueCoatProxySG( self._hostname, self._username, self._password, self._enable, connector_type=self._connector_type )
        assert type(self.device) == BlueCoatProxySG, 'object not match'
        assert self.device.connect() == True, 'could not connect to ' + self._hostname

    def testSystemConfig( self ):
        output = self.device.system.config.get()
        assert type( output ) == DeviceConfigurations, 'could not get running configuration'
    
    def _testSystemModel(self):
        # assert device.enableMode() == True, 'could enter enable mode'
        assert self.device.system.model.get() == ['WS-C3750-48TS', 'WS-C3750-24TS'], 'models do not match'
        assert self.device.system.firmware.version() == ['12.2(44)SE1', '12.2(44)SE1'], 'fw do not match'



if __name__ == "__main__":
    
    logging.basicConfig(level=logging.DEBUG)

    # suite = unittest.TestLoader().loadTestsFromTestCase(DeviceTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    
    # suite = unittest.TestLoader().loadTestsFromTestCase(CiscoIOSSwitchTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    # 
    # suite = unittest.TestLoader().loadTestsFromTestCase(CiscoIOSWirelessTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    
    # suite = unittest.TestLoader().loadTestsFromTestCase(CiscoCATOSNetworkDeviceTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    # 
    # suite = unittest.TestLoader().loadTestsFromTestCase(CiscoTopSpinOSNetworkDeviceTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
        
    # suite = unittest.TestLoader().loadTestsFromTestCase(DellSwitchTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)

    suite = unittest.TestLoader().loadTestsFromTestCase(CiscoASATestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
    
    # suite = unittest.TestLoader().loadTestsFromTestCase(CiscoContextASATestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    

    # suite = unittest.TestLoader().loadTestsFromTestCase(DigiTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    
    # suite = unittest.TestLoader().loadTestsFromTestCase(F5BigPipeTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    
    # suite = unittest.TestLoader().loadTestsFromTestCase(F5TMSHTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    
    # suite = unittest.TestLoader().loadTestsFromTestCase(AristaTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)

    # suite = unittest.TestLoader().loadTestsFromTestCase(BlueCoatTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)

    