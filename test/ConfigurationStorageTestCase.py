""" unittest for ssh network device """

from slac.ConfigurationStorage import ConfigurationStorage, ConfigurationFileDirectory, ConfigurationDatabase
from slac.DeviceConfigurations import DeviceConfigurations
from slac.Configuration import Configuration
import unittest
import logging
import shutil
import datetime
import os
from types import *


class ConfigurationStorageTestCase( unittest.TestCase ):

    _dbname = 'some_name'
    _dbhost = 'some_host'
    _dbuser = 'some_user'
    _dbpasswd = 'some_passwd'
    
    def testInit( self ):
        okay = None
        try:
            store = ConfigurationStorage( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
            okay = True
        except Exception, e:
            okay = False
            
        assert okay == True \
            and store._dbhost == self._dbhost \
            and store._dbname == self._dbname \
            and store._dbuser == self._dbuser \
            and store._dbpasswd == self._dbpasswd, "instantiation fail"

    def testConnect( self ):
        store = ConfigurationStorage( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        ret = None
        try:
            ret = store.connect()
        except Exception, e:
            pass
        assert ret == True, 'could not connect'
        
    def testDiffDifferent( self ):
        store = ConfigurationStorage( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        config_one = DeviceConfigurations(  )
        config_one.setConfig( ["hello there\n", "this is a test"] )
        config_two = DeviceConfigurations(  )
        config_two.setConfig( ["hello here\n", "this is a test"] )
        ret = store.isChanged( config_one, config_two )
        #logging.warn( diff )
        assert ret == True, "different configs showed no diff"

    def testDiffSame( self ):
        store = ConfigurationStorage( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        config_one = DeviceConfigurations(  )
        config_one.setConfig( ["hello there\n", "this is a test"] )
        config_two = DeviceConfigurations(  )
        config_two.setConfig( ["hello there\n", "this is a test"] )
        ret = store.isChanged( config_one, config_two )
        #logging.warn( diff )
        assert ret == False, "same configs showed different diffs"
        

    def testDetermineMergedContexts( self ):
        store = ConfigurationStorage( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )

        # create a device configuration o bject from teh raw strings
        config_one = DeviceConfigurations()
        config_one.setConfig( ["hello there\n", "this is a test"] )

        # construct a device configuration ob ject from a configuration object
        config_two = DeviceConfigurations()
        conf = Configuration( )
        conf.set( ["hello there\n", "this is a test"] )
        conf.setContext( 'something_else' )
        config_two.append( conf )
        array = store.determineMergedContexts( config_one, config_two )
        assert array == [ 'something_else', 'system' ], 'determining merged contexts failed: ' + str( array )
        
        
    def testGet( self ):
        """ there's a whole lot of types of gets we care about """
        # time range
        # version
        pass
        
    def testInsert( self ):
        """ """
        pass
        
        
class ConfigurationFileDirectoryTestCase( unittest.TestCase ):

    _dbname = '/tmp/net-config/config'
    _dbhost = None
    _dbuser = None
    _dbpasswd = None
    
    def testInit( self ):
        """ create object """
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        assert type(store) is ConfigurationFileDirectory \
            and store._dbname == self._dbname, 'error could not init object'

    def testConnect( self ):
       """ make sure it creates the correct directories """
       store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
       ret = store.connect()
       # delete
       shutil.rmtree( self._dbname )
       # check current directory
       if not store._CURRENT_DIRECTORY == self._dbname + '/' + store._CURRENT_DIRECTORY_SUFFIX:
           ret = False
       if not store._ARCHIVE_DIRECTORY == self._dbname + '/' + store._ARCHIVE_DIRECTORY_SUFFIX:
           ret = False
       assert ret == True, 'could not connect or internal path variables invalid: current=' + store._CURRENT_DIRECTORY + ', archive=' + store._ARCHIVE_DIRECTORY


    def testGetDate( self ):
        """ double check date output """
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        d = store._getDate()
        now = datetime.datetime.now()
        s = now.strftime("%Y-%m-%d")
        assert d == s, 'version parsing mismatch'
        
    def testSymLinkPathNoContext( self ):
        """ checking symlink paths """
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        host = 'hostname'
        p = store._getConfigSymlinkPath( host, None )
        q = self._dbname + '/current/' + host + '.config'
        assert p == q, 'symlinks with no context paths don\'t match: got=' + p +', expected=' + q


    def testSymLinkPathWithContext( self ):
        """ checking symlink paths with context"""
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        host = 'hostname'
        context = 'context_one'
        p = store._getConfigSymlinkPath( host, context )
        q = self._dbname + '/current/' + host + ':' + context + '.config'
        assert p == q, 'symlinks with context paths don\'t match: got=' + p +', expected=' + q

    def testGetConfigfilePathNoContextCurrentRevision( self ):
        """ checking filepath for no context, no revision"""
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        host = 'a'
        p = store._getConfigFilePath( host )
        q = self._dbname + '/current/' + host + '.config'
        assert p == q, 'filepath with no context paths, no revision don\'t match: got=' + p +', expected=' + q


    def testGetConfigfilePathWithContextCurrentRevision( self ):
        """ checking filepath for no context, no revision"""
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        host = 'a'
        context = 'something'
        p = store._getConfigFilePath( host, context=context )
        q = self._dbname + '/current/' + host + ':' + context + '.config'
        assert p == q, 'filepath with context paths, no revision don\'t match: got=' + p +', expected=' + q


    def testGetConfigfilePathWithContextKnownRevision( self ):
        """ checking filepath for with context, known revision"""
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        host = 'hostname'
        context = 'something'
        revision = '2009-01-01'
        p = store._getConfigFilePath( host, context=context, revision=revision )
        q = self._dbname + '/archive/' + host + '/' + host + ':' + context + '.config.' + revision 
        assert p == q, 'filepath with context paths, no revision don\'t match: got=' + p +', expected=' + q

    def testWriteConfig( self ):
        """ write raw text to a file """
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        filepath = '/tmp/netconfig-test'
        string = 'some config output goes here'
        store._writeConfig( string, filepath )
        # check 
        ret = os.path.exists( filepath )
        os.remove( filepath )
        assert ret == True, 'did not write raw file ' + filepath

    def testUpdateSymlink( self ):
        """ test symlinking files """
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        symlink = '/tmp/test_symlink'
        target = '/tmp/real_file'
        store._writeConfig( 'some config', target )
        store._updateSymlink( target, symlink )
        # TODO: further check?
        ret = os.path.exists( symlink )
        os.remove( symlink )
        os.remove( target )
        assert ret == True, 'could not update symlink successfully'
        


    def testSaveConfigWithContext( self ):
        """ save a configuration object """
        context = 'system' 
        hostname = 'example'
        revision = None
        config = Configuration( )
        config.set(  ['some text', 'goes here'] )
        config.setContext( context )
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        store.connect()
        store._saveConfig( hostname, config )
        # expected place for files
        filepath = store._getConfigFilePath( hostname, context, revision )
        ret = os.path.exists( filepath )
        #os.remove( filepath )
        assert ret == True, 'could not save config file with defined context: ' + filepath


    def testSaveConfigNoContext( self ):
        """ save a configuration object """
        context = None
        hostname = 'another'
        revision = None
        config = Configuration(  )
        config.set( ['some text', 'goes here'] )
        config.setContext( context )
        store = ConfigurationFileDirectory( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        store.connect()
        store._saveConfig( hostname, config )
        # expected place for files
        filepath = store._getConfigFilePath( hostname, context, revision )
        ret = os.path.exists( filepath )
        #os.remove( filepath )
        assert ret == True, 'could not save config file without context: ' + filepath



class ConfigurationDatabaseTestCase( unittest.TestCase ):

    _dbname = 'netconfig'
    _dbhost = 'sccs-dsneddon'
    _dbuser = 'netconfig_rw'
    _dbpasswd = 'Sc4rsC@n'

    def testInit( self ):
        """ test instantiation of configurationdatabase object """
        okay = None
        try:
            cdb = ConfigurationDatabase( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
            self._cdb = cdb
            okay = True
            
        except Exception, e:
            okay = False

        assert okay == True \
            and cdb._dbhost == self._dbhost \
            and cdb._dbname == self._dbname \
            and cdb._dbuser == self._dbuser \
            and cdb._dbpasswd == self._dbpasswd, "instantiation fail"

        #self._cdb = cdb

    def testAInsertDevice( self ):
        """ insert device into database """
        cdb = ConfigurationDatabase( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        cdb.createDevice( "test_device" )
        self.device_id = cdb._getDeviceByName
        
        assert self.device_id != None \
                and self.device_id != 0

    def testBAppendDeviceConfigurations( self ):
        """ add configurations to deviceconfigurations object """
        dc = DeviceConfigurations()
        conf = Configuration( )
        conf.set( ['hello there\n', 'this is a test'] )
        #conf.setContext( 'context_one' )
        dc.append( conf )
        confResult = dc.getConfig('system')
        conf2 = Configuration()
        conf2.set( ['hi there\n', 'this is also a test'] )
        conf2.setContext( 'context_two' )
        dc.append( conf2 )
        confResult2 = dc.getConfig('context_two')

        #logging.warn( "confResult.get()[0]: " + confResult.get()[0] )

        assert confResult.get()[0] == 'hello there\n' \
            and confResult2.get()[0] == 'hi there\n'

    def testCInsertConfiguration( self ):
        ''' add configuration to database '''
        cdb = ConfigurationDatabase( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        config = ["hello there\n", "this is a test"]
        cdb.insertConfig( 'test_device', config )
        config = cdb._getConfig ( "test_device" )

        assert len(config) > 0


    def testZDeleteDevice( self ):
        """ remove device from database """
        cdb = ConfigurationDatabase( dbhost=self._dbhost, dbname=self._dbname, user=self._dbuser, passwd=self._dbpasswd )
        device_id_old = cdb._getDeviceByName ( "test_device" )
        cdb.removeDevice( "test_device" )
        device_id = cdb._getDeviceByName( "test_device" )

        #logging.warn("Device ID: " + str(device_id))

        assert device_id_old != None \
                and device_id == None
    
    '''def testExample( self ):
        """ example of how to write a test unit """
        # do something, set up variables etc
        v = True
        
        # anyway, for primer of config:
        
        # create a config  object and give it a context
        config = Configuration( [ 'line 4', 'line 5', 'line 6' ] )
        config.setContext( 'context_name' )
        
        # create a device configurations object
        dc = DeviceConfigurations()
        # add the config object
        dc.append( config )
        
        # you prob wan tto test the following
        # 1) connection to db works with different args
        # 2) that the database has the correct tables (this should be in your connect/init method)
        # 3) you can store a device object
        # 4) you can store a config object, with and without context
        # 5) you can store a config object for a specified device
        # 6) you can get for all the 3 above
        # 7) your logging works for the rt, comment etc
        
        assert v == True, 'true did not return true!'
        '''

if __name__ == "__main__":
    
    #logging.basicConfig(level=logging.DEBUG)

    suite = unittest.TestLoader().loadTestsFromTestCase(ConfigurationStorageTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(ConfigurationFileDirectoryTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(ConfigurationDatabaseTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
    
