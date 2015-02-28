""" unittest for a configuration object """

from netconfig.Configuration import *
import unittest
import logging
from types import *
import datetime
from datetime import tzinfo
import tempfile
import os

from pprint import pprint

def _compareArrays( x, y ):
    # copy so we don't affect hte originals
    one = []
    two = []
    for a in x:
        one.append(a)
    for b in y:
        two.append(b)
    total = 0
    for i in one:
        j = two.pop(0)
        # logging.error( "I: " + i )
        # logging.error( "J: " + j )
        this = cmp( i, j )
        total = total + this
    return total
    

class BigIPLTMTestCase( unittest.TestCase ):
    
    def testInit( self ):
        config = None
        try:
            config = BigIPLTMConfiguration( )
        except Exception, e:
            pass
        assert type(config) is BigIPLTMConfiguration, "instantiation fail"

    def testFromUCSFile( self ):
        f = '/tmp/rtr-lbserv03-01-new_config.ucs'
        config = BigIPLTMConfiguration( f )
        assert type(config) is BigIPLTMConfiguration, "instantiation fail"

    def testUCSCompareSame( self ):
        config1 = BigIPLTMConfiguration( '/tmp/rtr-lbserv03-01-new_config.ucs' )
        config2 = BigIPLTMConfiguration( '/tmp/another.ucs' )
        assert config1 == config2, 'not same with equals'
        assert cmp( config1, config2 ) == 0, 'not same with cmp'



    def testUCSCompareDifferent( self ):
        config1 = BigIPLTMConfiguration( '/tmp/rtr-lbserv03-01-new_config.ucs' )
        config2 = BigIPLTMConfiguration( '/tmp/different.ucs' )
        assert not config1 == config2, 'not same with equals'
        assert not cmp( config1, config2 ) == 0, 'not same with cmp'



class ConfigurationTestCase( unittest.TestCase ):

    config_one = [ 'line 1', 'line 2', 'line 3' ]
    config_two = [ 'line 4', 'line 5', 'line 6' ]
    config_three = [ 'line 1', 'line 4', 'line 3' ]
    
    def testInit( self ):
        """ object creation """
        config = None
        try:
            config = Configuration( )
        except Exception, e:
            pass
        assert type(config) is Configuration, "instantiation fail"

    def testConfigInstantiate( self ):
        """ create new config """
        config = Configuration(  )
        config.set( self.config_one )
        res = _compareArrays( config.get(), self.config_one )
        assert res == 0, "different configs on instantiation " + str(res)

    def testConfigFromFile( self ):
        # create file
        # logging.error("CONF: " + str(self.config_one))
        temp, path = tempfile.mkstemp()
        f = open( path, 'w' )
        for l in self.config_one:
            f.write( l + "\n" )
        f.close()
        # assign to object
        config = Configuration( )
        config.set( path )
        # logging.error("FILE: " + str(config.get()))
        
        res = _compareArrays( config.get(), self.config_one )
        os.remove( path )
        assert res == 0, 'different configs for file'


    def testConfigSet( self ):
        """ setting config """
        config = Configuration( )
        this = []
        for i in self.config_one:
            this.append( i )

        config.set( self.config_one )
        total = _compareArrays( this, self.config_one )
        assert total == 0, "different configs on set"

    def testStr( self ):
        """ test string output """
        config = Configuration(  )
        config.set( self.config_one )
        this = str(config) # we force that we have newlines after each line
        # map that to have newlines - not forgetting last newline
        that = "\n".join(self.config_one) + "\n"
        assert this == that, 'str() is different; this: ' + this + ", that: " + that
    
    def testCmpSame( self ):
        """ cmp of same configs """
        one = Configuration(  )
        one.set( self.config_one )
        two = Configuration(  )
        two.set( self.config_one )
        assert cmp( one, two ) == 0, 'cmp() failed'

    def testCmpDifferent( self ):
        """ cmp of different configs """
        one = Configuration(  )
        one.set( self.config_one )
        two = Configuration(  )
        two.set( self.config_two )
        assert not cmp( one, two ) == 0, 'cmp() failed'
        
    def testDiffSame( self ):
        """ diff of same configs """
        one = Configuration(  )
        one.set( self.config_one )
        two = Configuration(  )
        two.set( self.config_one )
        assert len( one.diff( two ) ) == 0, 'diff() with idential failed'

    def testDiffDifferent( self ):
        """ diff of different configs"""
        one = Configuration(  )
        one.set( self.config_one )
        two = Configuration(  )
        two.set( self.config_one )
        diff = one.diff( two )
        # assert len(diff) == 0, 'no differences ('+str(pprint(diff))+')'

        manual_diff = [ '---  \n', '+++  \n', '@@ -1,3 +1,3 @@\n', '-line 1\n', '-line 2\n', '-line 3\n', '+line 4\n', '+line 5\n', '+line 6\n']
        check = 0
        for i in diff:
            #logging.error( "'" + i + "'")
            j = manual_diff.pop(0)
            if not i == j:
                logging.error( "-->\ni='" + i + '\'\nj=\n' + j + "\'")
                check = check + 1
        assert check == 0, 'diff() with different failed'


    def testConvertDate( self ):
        """ test time convesion """
        string = '11:27:21 PST Tue Dec 1 2009'
        one = Configuration()
        dt = one._convertDate( string )
        #logging.error( 'IN: ' + str(dt) )
        class pst( tzinfo ):
            def tzname( self, dt ):
                return 'PST'
            def utcoffset( self, dt ):
                return datetime.timedelta( hours=-8 )
            def dst( self, dt ):
                return datetime.timedelta(0)
        correct = datetime.datetime( 2009, 12, 1, 11, 27, 21, tzinfo=pst())
        #logging.error( "OUT: " + str(correct) )
        assert dt == correct, 'convert timestamp failed'

    def testGetWithIgnore( self ):
        """ return config without certain lines """
        c = Configuration( )
        c.set( self.config_one )
        conf = c.get( ignore_lines=[0,2] )
        #logging.error( conf )
        assert conf == [ 'line 2'], 'get with ignore lines failed'
    
    def testGet( self ):
        """ return all config """
        c = Configuration(  )
        c.set( self.config_one )
        conf = c.get()
        assert conf == self.config_one, 'get raw config'



class ContextualDiffTestCase( unittest.TestCase ):

    config_one = [ 'config line 1', 'config line 2', 'config line 3' ]
    config_two = [ 'config line 4', 'config line 5', 'config line 6' ]
    config_three = [ 'config line 1', 'config line 4', 'config line 3' ]
    config_indent1 = [ 'interface 1', '  int line 1', '  int line 2', '  int line 3' ]
    config_indent2 = [ 'interface 1', '  int line 1', '  int line 4', '  int line 3' ]


    config_cisco1 = [ 
            '! Last configuration change at 11:27:21 PST Tue Dec 1 2009 by jaredg',
            '! NVRAM config last updated at 11:27:47 PST Tue Dec 1 2009 by jaredg',
            '!',                                # 0
            'interface GigabitEthernet1/5',
            ' description something',
            ' switchport',
            ' switchport access vlan 164',      
            ' switchport mode access',          # 5
            ' switchport nonegotiate',
            ' logging event link-status',
            ' logging event trunk-status',
            ' logging event bundle-status', 
            ' storm-control broadcast level 0.10', #10
            ' storm-control multicast level 0.10',
            ' spanning-tree portfast edge', 
            ' spanning-tree bpduguard enable',  
            ' hold-queue 1000 in',
            ' hold-queue 1000 out',              # 15
            '!',
            'upgrade fpd auto',
            'version 12.2',
            'service nagle',
            'no service pad',
            'service tcp-keepalive' ]

    config_cisco2 = [ 
            '! Last configuration change at 11:27:21 PST Tue Dec 2 2009 by jaredg',
            '! NVRAM config last updated at 12:47:10 PST Tue Dec 1 2009 by ytl',
            '!',
            'interface GigabitEthernet1/5',
            ' description another thing',
            ' switchport',
            ' switchport access vlan 164',
            ' switchport mode access',
            ' switchport nonegotiate',
            ' logging event link-status',
            ' logging event trunk-status',
            ' logging event bundle-status',
            ' storm-control broadcast level 0.10',
            ' storm-control multicast level 0.10',
            ' spanning-tree portfast edge',
            ' spanning-tree bpduguard enable',
            ' hold-queue 200 in',
            ' hold-queue 200 out',
            '!',
            'upgrade fpd auto',
            'version 12.2',
            'service nagle',
            'no service pad',
            'service tcp-keepalive' ]

    # def testNoStanza( self ):
    #     """ contextual diff """
    #     c1 = Configuration()
    #     c1.set( self.config_one )
    #     c2 = Configuration()
    #     c2.set( self.config_two )
    #     c1.contextual_diff( c2 )
    # 
    # def testStanza( self ):
    #     """ contextual diff """
    #     c1 = Configuration()
    #     c1.set( self.config_indent1 )
    #     c2 = Configuration()
    #     c2.set( self.config_indent2 )
    #     c1.contextual_diff( c2 )
    #     
    # def testCisco( self ):
    #     c1 = CiscoIOSConfiguration()
    #     c1.set( self.config_cisco1 )
    #     c2 = CiscoIOSConfiguration()
    #     c2.set( self.config_cisco2 )
    #     c1.contextual_diff( c2 )
        
    
    def testRealIOS( self ):
        """ test simple interface change """
        c1 = CiscoIOSConfiguration()
        c1.set( '/u/sf/ytl/net/configs/archive/swh-b084f1/swh-b084f1.config.2012-02-20' )
        c2 = CiscoIOSConfiguration()
        c2.set( '/u/sf/ytl/net/configs/archive/swh-b084f1/swh-b084f1.config.2012-02-24' )
        c1.contextual_diff( c2 )


    # def testRealASA( self ):
    #     """ test simple interface change """
    #     c1 = CiscoASAConfiguration()
    #     c1.set( '/u/sf/ytl/net/configs/archive/rtr-fwpbx01/rtr-fwpbx01.config.2011-12-13' )
    #     c2 = CiscoASAConfiguration()
    #     c2.set( '/u/sf/ytl/net/configs/archive/rtr-fwpbx01/rtr-fwpbx01.config.2012-02-15' )
    #     c1.contextual_diff( c2 )



class IOSConfigurationTestCase( unittest.TestCase ):
    
    config_one = [ '!', 
            '! Last configuration change at 11:27:21 PST Tue Dec 1 2009 by jaredg',
            '! NVRAM config last updated at 11:27:47 PST Tue Dec 1 2009 by jaredg',
            '!',
            'upgrade fpd auto',
            'version 12.2',
            'service nagle',
            'no service pad',
            'service tcp-keepalive' ]

    config_two = [ '!', 
            '! Last configuration change at 11:27:21 PST Tue Dec 2 2009 by jaredg',
            '! NVRAM config last updated at 12:47:10 PST Tue Dec 1 2009 by ytl',
            '!',
            'upgrade fpd auto',
            'version 12.2',
            'service nagle',
            'no service pad',
            'service tcp-keepalive' ]
    
    def testCommentLineNumbers( self ):
        """ determine comment line numbers """
        c = CiscoIOSConfiguration(  )
        c.set( self.config_one )
        array, change, save = c.getCommentLineInfo()
        assert array == [1,2] \
            and change == c._convertDate('11:27:21 PST Tue Dec 1 2009') \
            and save == c._convertDate('11:27:47 PST Tue Dec 1 2009'), 'comment line numbers don\'t match'

    def testCommitUpToDateTrue( self ):
        """ test config save is upto date """
        c = CiscoIOSConfiguration(  )
        c.set( self.config_one )
        assert c.isCommitUpToDate() == True, 'up-to-date commit failed'

    def testCommitUpToDateFalse( self ):
        """ test config save is not upto date """
        c = CiscoIOSConfiguration(  )
        c.set( self.config_two )
        assert c.isCommitUpToDate() == False, 'up-to-date commit failed'


    def testDiffIgnoreComments( self ):
        """ test diff without comments """
        c1 = CiscoIOSConfiguration(  )
        c1.set( self.config_one )
        c2 = CiscoIOSConfiguration(  )
        c2.set( self.config_one )
        d = c1.diff( c2, ignore_comments=True )
        assert len(d) == 0, 'diff ignoring comments failed'

    def testDiffWithComments( self ):
        """ test diff with comments """
        
        # TODO: doens't work.. why?
        
        c1 = CiscoIOSConfiguration(  )
        c1.set( self.config_one )
        c2 = CiscoIOSConfiguration(  )
        c2.set( self.config_two )
        d = c1.diff( c2 )
        logging.error( d )
        assert len(d) > 0, 'diff ignoring comments failed'


if __name__ == "__main__":
    
    logging.basicConfig(level=logging.DEBUG)

    # suite = unittest.TestLoader().loadTestsFromTestCase(ConfigurationTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    # 
    # suite = unittest.TestLoader().loadTestsFromTestCase(IOSConfigurationTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)

    # suite = unittest.TestLoader().loadTestsFromTestCase(BigIPLTMTestCase)
    # unittest.TextTestRunner(verbosity=2).run(suite)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(ContextualDiffTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
