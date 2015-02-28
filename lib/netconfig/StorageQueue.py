#from __future__ import with_statement
import logging
# import MySQLdb
import types
import re
import sys
import os
import time
import ConfigParser


class StorageQueueException( Exception ):

    def __init__( self, value ):
        self.value = value

    def __str__( self ):
        return repr( self.value )



class StorageQueue( object ):
    """
    Object to represent the need to store the configurations of a device
    we use a directory housing indiviual files that represent 'tickets' of each queue item to be committed
    we have a daemon() method to spawn a daemon that will monitor the contents of this directory and 
    commit the relevant changes into the configurationstorage objects
    we have a queue() method that puts tickets into the directory
    """
    
    TICKET_DIRECTORY = None
    
    TICKET_SECTIONNAME = 'NETCONFIG TICKET'
    
    def __init__( self, path=None ):
        """ init and set directory """
        if not path:
            path = '/tmp/net-config_storage-queue'
        self.TICKET_DIRECTORY = path
        self._makedir( self.TICKET_DIRECTORY )

        
    def _makedir( self, d ):
        if not os.path.exists( d ):
            logging.debug( 'making directory ' + str( d ) )
            os.makedirs( d )
    
    def _getTicketFilename( self, hostname ):
        """ unique ticket filepath """
        now = int(time.time())
        filename = str(now) + '_' + hostname
        filepath = self.TICKET_DIRECTORY + '/' + filename
        return filepath
    
    def _getHostFromFilename( self, filename ):
        out = filename.split('_')
        return out[len(out)-1]
    
    def _setTicket( self, storage_ticket ):
        """ use the config aprser object """
        # use config parser
        c = ConfigParser.ConfigParser()
        c.add_section( self.TICKET_SECTIONNAME )

        hostname = None
        user = None
        rt = None
        comment = None
        if storage_ticket.user == None:
            user = ''
        else:
            user = storage_ticket.user
        if storage_ticket.rt == None:
            rt = ''
        else:
            rt = storage_ticket.rt
        if storage_ticket.comment == None:
            comment = ''
        else:
            comment = storage_ticket.comment

        c.set( self.TICKET_SECTIONNAME, 'user', str(user) )
        c.set( self.TICKET_SECTIONNAME, 'rt', str(rt) )
        c.set( self.TICKET_SECTIONNAME, 'comment', str(comment) )
        
        return c
        
    def _createTicket( self, storage_ticket ):
        """ actually create the file """

        ticket = self._setTicket( storage_ticket )
        filename = self._getTicketFilename( storage_ticket.hostname )
        logging.debug( "saving ticket " + filename )
        # doesn't work with 2.4.3 python
        # with open( filename, 'wb' ) as fh:
        #     ticket.write( fh )
        fh = open( filename, 'wb' )
        ticket.write( fh )
        fh.close()

        return filename
    
    
    def _getTicket( self, filename ):
        """ given filename, create a ticket object """
        c = ConfigParser.ConfigParser()
        c.read( filename )
        return c
        
    def queue( self, storage_ticket ):
        """ queue the item to be inserted into the queue """
        logging.debug("queuing ticket for " + str(storage_ticket.hostname) + ", user=" + str(storage_ticket.user) + ", rt=" + str(storage_ticket.rt) + ", comment=" + str(storage_ticket.comment) )
        self._createTicket( storage_ticket )

    def list( self ):
        l = os.listdir( self.TICKET_DIRECTORY )
        l.sort(reverse=True)
        return l
        
    def get( self, filename ):
        """ get the next item in the queue """
        logging.debug( "got next as " + filename )
        t = self._getTicket( filename )
        # TODO: spearate queue for in process?
        os.unlink( filename )

        host = self._getHostFromFilename( ticket )
        user = t.get( self.TICKET_SECTIONNAME, 'user' )
        rt = t.get( self.TICKET_SECTIONNAME, 'rt' )
        comment = t.get( self.TICKET_SECTIONNAME, 'comment' )

        ticket = StorageTicket( host, user, rt, comment )
        return ticket
    

    