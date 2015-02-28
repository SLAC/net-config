""" unittest for a configuration object """

from slac.DeviceConfigurations import DeviceConfigurations
from slac.Configuration import Configuration
import unittest
import logging
from types import *

default_context = 'system'

class DeviceConfigurationsTestCase( unittest.TestCase ):

    config_line = [ 'line 1\n', 'line 2\n', 'line 3\n' ]
    config_one = Configuration( )
    config_one.set( config_line )
    config_two = Configuration( )
    config_two.set( [ 'line 4\n', 'line 5\n', 'line 6\n' ] )
    config_three = Configuration( )
    config_three.set( [ 'line 1\n', 'line 4\n', 'line 3\n' ] )

    def testInit( self ):
        dc = None
        try:
            dc = DeviceConfigurations( )
        except Exception, e:
            pass
        assert type(dc) is DeviceConfigurations, "instantiation fail " + str(type(dc))

    def testDefaultContext( self ):
        dc = DeviceConfigurations( )
        assert dc.default_context == default_context, 'default context changed'

    def testConfigInstantiate( self ):
        dc = None
        dc = DeviceConfigurations( )
        dc.setConfig( self.config_line )
        a = dc.getContexts()
        assert len(a) == 1 and a[0] == default_context, 'single config on intantiate doenst work'

    def testContext( self ):
        dc = DeviceConfigurations()
        string =  'test_context'
        dc.setConfig( self.config_one, context=string )
        assert dc.getContexts()[0] == string, 'context names do not match'

    def testAppend( self ):
        dc = DeviceConfigurations()
        try:
            dc.append( self.config_one )
        except Exception, e:
            logging.error( 'FAILURE: append failed ' + str(dc.getContexts()) + ': ' + str(e) )
            
        assert len(dc.getContexts()) == 1 and cmp( dc.getConfig(), self.config_one ) == 0, 'append failed; contexts ' + str(dc.getContexts())

    def testCmpSame( self ):
        dc1 = None
        dc2 = None
        dc1 = DeviceConfigurations( )
        dc1.setConfig( self.config_line )
        dc2 = DeviceConfigurations(  )
        dc2.setConfig( self.config_line )
        assert cmp( dc1, dc2 ) == 0, 'cmp() with same failed'
        
        
    def testCmpDifferent( self ):
        dc1 = None
        dc2 = None
        dc1 = DeviceConfigurations( )
        dc1.setConfig( self.config_line )
        dc2 = DeviceConfigurations( )
        dc2.append( self.config_two )
        c = cmp( dc1, dc2 )
        assert not c == 0, 'cmp() with different failed (' + str(c) + '): \ndc1=' + str( dc1 ) +"\ndc2=" + str( dc2 )

    def testDiffSame( self ):
        dc1 = None
        dc2 = None
        dc1 = DeviceConfigurations(  )
        dc1.setConfig( self.config_line )
        dc2 = DeviceConfigurations(  )
        dc2.setConfig( self.config_line )
        diff = dc1.diff( dc2 )
        assert len(diff) == 0, 'diff() of same failed'


    def testDiffDifferent( self ):
        dc1 = None
        dc2 = None
        dc1 = DeviceConfigurations(  )
        dc1.setConfig( self.config_line )
        dc2 = DeviceConfigurations( )
        dc2.append( self.config_three )
        diff = dc1.diff( dc2 )
        assert len(diff) > 0, 'diff() of different failed'


if __name__ == "__main__":
    
    #logging.basicConfig(level=logging.DEBUG)

    suite = unittest.TestLoader().loadTestsFromTestCase(DeviceConfigurationsTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
    
