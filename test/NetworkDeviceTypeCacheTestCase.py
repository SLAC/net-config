""" unittest for network device type cache """

from slac.NetworkDeviceTypeCache import NetworkDeviceTypeCache
import slac.netconfig
import unittest
import logging
import ConfigParser
from types import *

class NetworkDeviceTypeCacheTestCase( unittest.TestCase ):

    defaults_file = '/afs/slac.stanford.edu/g/scs/net/projects/net-config/config/netconfig.py';

    def getProfile( self, profile_name ):
        profile = slac.netconfig.getProfile( self.defaults_file, profile_name )
        profile = slac.netconfig.parsePasswords( profile )
        #logging.debug( str(profile) )
        return profile
        
    def testTryGoodIOS( self ):
        # get teh cache
        cache = NetworkDeviceTypeCache( None )
        
        # get the profile
        profile = self.getProfile( 'ios' )
        success = cache.attempt( 'swh-b050f1', profile )
        
        assert success == True, "found good ios device"

    def testTryBadIOS( self ):
        # get teh cache
        cache = NetworkDeviceTypeCache( None )

        # get the profile
        profile = self.getProfile( 'ios' )
        success = cache.attempt( 'swh-core1old', profile )

        assert success == False, "found bad ios device"

    def testTryGoodCATOS( self ):
        # get teh cache
        cache = NetworkDeviceTypeCache( None )

        # get the profile
        profile = self.getProfile( 'catos' )
        success = cache.attempt( 'swh-core1old', profile )

        assert success == True, "found good catos device"

    def testTryBadCATOS( self ):
        # get teh cache
        cache = NetworkDeviceTypeCache( None )

        # get the profile
        profile = self.getProfile( 'catos' )
        success = cache.attempt( 'swh-b050f1', profile )

        assert success == False, "found bad catos device"


    def testTryGoodCATOS( self ):
        # get teh cache
        cache = NetworkDeviceTypeCache( None )

        # get the profile
        profile = self.getProfile( 'ib' )
        success = cache.attempt( 'swh-ibfarmcore1', profile )

        assert success == True, "found good ib device"

    def testTryBadCATOS( self ):
        # get teh cache
        cache = NetworkDeviceTypeCache( None )

        # get the profile
        profile = self.getProfile( 'ib' )
        success = cache.attempt( 'swh-b050f1', profile )

        assert success == False, "found bad ib device"


    def testStoreCache( self ):
        
        cache = NetworkDeviceTypeCache( None )
        
        host = 'test-host'
        profile = 'fake-profile'
        cache.store( host, profile )

        # now retrieve
        retrieved_profile = cache.get( host )
        assert profile == retrieved_profile, "cache store failed"
        

    def testSaveCache( self ):
        
        cache_file = '/tmp/NetworkDeviceTypeCache.cache'
        cache = NetworkDeviceTypeCache( cache_file )
        
        # create some dummy data
        cache.store( 'host1', 'profile1' )
        cache.store( 'host2', 'profile2' )
        cache.store( 'host3', 'profile3' )
        
        cache.save()
        
        # open file manually and populate with config parser
        config = ConfigParser.RawConfigParser()
        config.read( cache_file )
        
        i = 0
        for k,v in config.items( 'profile_cache' ):
            if k == 'host1' and v == 'profile1':
                i = i + 1
            elif k == 'host2' and v == 'profile2':
                i = i + 1
            elif k == 'host3' and v == 'profile3':
                i = i + 1

        assert i == 3, 'saving cache file failed ' + str(i)


if __name__ == "__main__":
    
    #logging.basicConfig(level=logging.DEBUG)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(NetworkDeviceTypeCacheTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)