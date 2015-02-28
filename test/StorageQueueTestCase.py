""" unittest for a configuration object """


import unittest
import logging
import os
from types import *
import time
from slac.StorageQueue import StorageQueue
import ConfigParser

class StorageQueueTestCase( unittest.TestCase ):
    
    def testInstantiateNoPath( self ):
        """ get ticket filename with no arguments """
        s = StorageQueue()
        # shoudl create directory at '/tmp/net-config_storage-queue'
        d = '/tmp/net-config_storage-queue'
        ret = os.path.exists( d )
        os.removedirs( d )
        assert ret == True, 'instantiation did not create directory ' + d

    def testInstantiateWithPath( self ):
        """ get ticket filename with """
        d = '/tmp/new-dir-path'
        s = StorageQueue( d )
        ret = os.path.exists( d )
        os.removedirs( d )
        assert ret == True, 'instantiation did not create directory ' + d

    def testGetTicketFilename( self ):
        """ get a ticket filename """
        d = '/tmp/test'
        s = StorageQueue( d )
        hostname = 'some-host'
        ret = s._getTicketFilename( hostname ) 
        now = int(time.time())
        
        expected = d + '/' + str(now) + '_' + hostname
        os.removedirs( d )
        
        assert ret == expected, 'ticket filename did not match expected: got=' + ret + ", expected=" + expected
        

    def testCreateTicket( self ):
        """ create a ticket """
        d = '/tmp/test'
        s = StorageQueue( d )
        hostname = 'some-host'
        user = 'person'
        rt = '12345'
        comment = 'some random bit of text'
        
        section = s.TICKET_SECTIONNAME
        
        ticket = s._createTicket( hostname, user, rt, comment )
        
        # use config read to get
        c = ConfigParser.ConfigParser()
        c.read( ticket )
        truth = False
        if c.get( section, 'user' ) == user \
            and c.get( section, 'rt' ) == rt \
            and c.get( section, 'comment' ) == comment:
            truth = True
        os.unlink( ticket )
        os.removedirs( d )
        assert truth == True, 'ticket did not match expected input'
    
    def testStripHost( set ):
        """ derive host from filname """
        d = '/tmp/test'
        s = StorageQueue( d )
        hostname = 'some-host'
        ret = s._getTicketFilename( hostname ) 
        os.removedirs( d )
        assert s._getHostFromFilename( ret ) == hostname, 'could not determine hostname from ticket'

    
if __name__ == "__main__":
    
    #logging.basicConfig(level=logging.DEBUG)

    suite = unittest.TestLoader().loadTestsFromTestCase(StorageQueueTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
