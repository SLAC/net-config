import logging
import types
import os
import errno
import datetime

from netconfig.backup.configuration import DeviceConfigurations
from netconfig.util import getUsername


#######################################################################
# storage exceptions
#######################################################################

class StorageQueueException( Exception ):
    def __init__( self, value ):
        self.value = value
    def __str__( self ):
        return repr( self.value )

class ConfigurationStorageException( Exception ):
    def __init__( self, value ):
        self.value = value
    def __str__( self ):
        return repr( self.value )

class ConfigurationStorageWarning( Exception ):
    def __init__( self, value ):
        self.value = value
    def __str__( self ):
        return repr( self.value )


class Store( object ):
    """
    Base class for the storage of configuration files from devices
    
    uses the DeviceConfigurations object to represent all configurations for a specific device
    each DeviceConfigurations object has one or more Configuration object (for each context)
    
    """
    
    name = None

    def __init__( self, **kwargs ):
        """Initialize class with default parameters """
        for k,v in kwargs.iteritems():
            setattr( self, k, v )

    def connect( self ):
        """ connects to the database """
        return True

    def __enter__(self):
        self.connect()
    
    def close(self):
        """Close SQL Connection"""
        pass        

    def __exit__(self):
        self.close()

    def determineMergedContexts( self, device_config_one,  device_config_two):
        contexts = {}
        if len(contexts) == 0:
            c1 = device_config_one.getContexts()
            for c in c1:
                contexts[c] = True
            
            c2 = device_config_two.getContexts()
            for c in c2:
                contexts[c] = True

        out = []
        for c in contexts:
            if contexts[c]:
                out.append( c )
                
        return out
    
    
    def diff( self, device_config_one, device_config_two, ignore_comments=False, contexts=[], ):
        """ works out the diffs between the two configs objects and returns a dict of each diff """
        # logging.debug("DC diff... %s %s" % (device_config_one, device_config_two))
        if len( contexts ) == 0:
            contexts = self.determineMergedContexts( device_config_one, device_config_two )
        # logging.debug("  contexts: %s" % (contexts,) )
        # logging.error( "BEFORE DIFF:\n  old=" + str(device_config_one._configs[0]._config[:5]) + "\n  new=" +str(device_config_two._configs[0]._config[:5]))
        d = device_config_one.diff( device_config_two, contexts=contexts, ignore_comments=ignore_comments )
        # logging.error( "AFTER DIFF:\n  old=" + str(device_config_one._configs[0]._config[:5]) + "\n  new=" +str(device_config_two._configs[0]._config[:5]))
        # logging.debug( 'diff is %s' %(d,) )
        if len(d) > 0:
            return True, d
        return False, d
    
    def is_changed( self, device_config_one, device_config_two, ignore_comments=True ):
        res, diff = self.diff( device_config_one, device_config_two, ignore_comments=ignore_comments )
        return res
    
    def insert( self, hostname, device_config, revision=None, user=None, rt=None, comment=None ):
        """ inserts a new configuration (create) """
        pass

    def get( self, hostname, revision=None):
        """ retrieves the config for host with revision number (none for latest) (read)"""
        pass
        
    def update( self, hostname, device_config, revision=None ):
        """ updates an existing device config, if revision is none, update most recent """
        pass
    
        
    def delete( self, hostname, revision=None ):
        """ removes the config from the database (delete) """
        pass


class FileStore( Store ):
    """
    implementation of configuration storage in a directory somewhere
    keeps history of changes as files
    
    BASE_DIRECTORY=/afs/slac.stanford.edu/g/scs/net/net-config/config
    CONFIG_DIRECTORY=$BASE_DIRECTORY/config
    
    stores under:
    CONFIG_DIRECTORY/current/{hostname}.config  (symlink to below)
    CONFIG_DIRECTORY/{rtr|swh|ap}/{hostname}/{hostname}.config.{date}
    
    """

    name = 'storage-file'

    _CURRENT_DIRECTORY_SUFFIX = 'current'
    _ARCHIVE_DIRECTORY_SUFFIX = 'archive'
    _CURRENT_DIRECTORY = ""
    _ARCHIVE_DIRECTORY = ""

    def __init__( self, **kwargs ):
        # always localhost for database location
        # logging.error("KWARGS: %s" % (kwargs,))
        super( FileStore, self ).__init__( **kwargs )
        self._CURRENT_DIRECTORY = self.path + '/' + self._CURRENT_DIRECTORY_SUFFIX
        self._ARCHIVE_DIRECTORY = self.path + '/' + self._ARCHIVE_DIRECTORY_SUFFIX                

    def _makedir( self, d ):
        if not os.path.exists( d ):
            logging.debug( 'making directory ' + str( d ) )
            os.makedirs( d )
    
    def connect( self ):
        """ instantiate filesystem """
        # use self._dbname as CONFIG_DIRECTORY
        self._makedir( self._dbname )
        # make current directory for symlinks
        self._makedir( self._CURRENT_DIRECTORY )
        # make current directory for actual config storage
        self._makedir( self._ARCHIVE_DIRECTORY )
        
        return True

    def disconnect( self ):
        # flush all writes
        pass

    def _get_date( self ):
        """ returns current datestamp for storage """
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d_%H:%M")


    def _get_config( self, hostname, context=None, revision=None ):
        """ returns the configuration object for the given """
        filepath = self.__get_config_file_path( hostname, context=context, revision=revision )
        logging.debug("  filepath: %s" % (filepath,))
        # follow symlink
        filepath = os.path.realpath( filepath )
        return filepath
        
        # this_config = []
        # if os.path.exists( filepath ):
        #     f = open( filepath, 'r' )
        #     while 1:
        #         l = f.readline()
        #         if not l:
        #             break
        #         # we assume that we must strip off the \n at end (see _writeConfig)
        #         this_config.append( l.rstrip('\n') )
        #     f.close( )
        #     #logging.debug( "CONFIG: " + config )
        # else:
        #     return None
        # return this_config

    def get_contexts( self, hostname ):
        """ determine what contexts exist for the hostname """
        # TODO: scan through directory for host?
        return ['system']

    # def _determine_device_type( self, hostname ):
    #     """ given the config type, return the device type as per the profiles """
    #     logging.error("DEVICE TYPE FOR %s" % (hostname,))
    # 
    #     raise ConfigurationStorageException, "could not determine configuration type"

    def get( self, hostname, contexts=[], revision=None, ref_type=None ):
        """ retrieves the configs from the disk and spits out a device configurations object """
        dc = DeviceConfigurations( )
        if len(contexts) == 0:
            contexts = self.getContexts( hostname )
        
        # add configs
        for c in contexts:
            logging.debug( "getting config object for context " + c )
            conf = self._get_config( hostname, context=c, revision=revision )
            # if the config doens't already exist, then config == None
            if not conf:
                logging.debug( '  no configuration found for context ' + c )
            # if the item (file) doesn't exist, then skip
            elif not os.path.isfile( conf ):
                logging.debug('  configuration file does not exist')
                pass
            else:
                # determine the config type
                logging.debug( "  adding configuration for context " + c )
                # logging.error("REF TYPE %s" % (type(ref_type.getConfig(c)) ) )
                dc.setConfig( conf, config_type=ref_type.getConfig(c), context=c )

        #logging.debug( "GOT DC: " + str(dc))
        return dc
        
    
    def __get_config_symlink_path( self, hostname, context ):
        """ return the symlink path for the hostname and context """
        path = self._CURRENT_DIRECTORY + '/'
        f = hostname + '.config'
        if context:
            f = hostname + ':' + context + '.config'
        p = os.path.join( path, f )
        logging.debug( "  symlink path: %s (%s)" % (p,self._CURRENT_DIRECTORY) )
        return p
    
    
    def validateContext( self, context ):
        """ bit of a hack to determine what the default_context should be """
        if context == 'system':
            return None
        return context
        
        
    def __get_config_file_path( self, hostname, context=None, revision=None ):
        """ returns the path for the config revision, None -> current """
        # get the config from symlink if revision is None
        logging.debug( "getting config file path for hostname: %s, rev: %s" % (hostname,revision))

        context = self.validateContext( context )

        if revision == None:
            path = self.__get_config_symlink_path( hostname, context )
            logging.debug("  no revision: current config for " + path)
            return path

        # add full path
        else:
            
            path = self._ARCHIVE_DIRECTORY + '/' + hostname + '/'
            f = hostname + '.config' + '.' + revision
            # need longer form for contexts
            if context:
                f = hostname + '\:' + context + '.config' + '.' + revision

            # logging.error( "config for " + path )
            return os.path.join( path, f )

    def _write_config( self, config, filepath ):
        """ writes the configuration string to the filepath """
        # TODO: use DeviceConfigurations object?
        # make sure the dir exists
        logging.debug( "writing configuration to " + filepath )
        d = os.path.dirname( filepath )
        self._makedir ( d)
        f = open( filepath, 'w')
        data = config.get()
        if type(data) == list:
            # logging.error("LIST: " + str(data[:5]))
            for i in data:
                f.write( i + "\n" )
        else:
            f.write( data )
        f.close( )
        return True
    
    def __update_symlink( self, target, symlink ):
        """ relinks the symlink to the revision provided, None means newest """
        d = os.path.dirname( symlink )
        self._makedir( d )

        # remoev existing symlink
        if os.path.exists( symlink ):
            os.remove( symlink )
        # make sure we point to valid targe
        if not os.path.isfile( target ):
            return False

        res = None
        try:
            res = os.symlink( target, symlink )
        except OSError, e:
            # logging.error("symlinking error: %s %s" % (type(e),e))
            os.remove( symlink )
            res = os.symlink( target, symlink )

        return res

    def __save_config( self, hostname, config ):
        """ dumps the config into the filepath """
        
        context = self.validateContext( config.getContext() )
        revision = config.get_revision()
        # path for saving - ensure we have the date if no revision exists
        this_revision = None
        if not revision:
            this_revision = self._get_date()
        
        filepath = self.__get_config_file_path( hostname, context, this_revision )
        
        # write config and update symlinks
        self._write_config( config, filepath )

        # update the current symlink
        if not revision:
            logging.debug( "updating current symlink")
            symlink = self.__get_config_symlink_path( hostname, context )
            self.__update_symlink( filepath, symlink )
        
        return True


    def _save( self, hostname, device_configurations, revision=None ):
        """ write the dc to disk """
        for context in device_configurations.getContexts():
            
            # don't boher with system context
            if context == DeviceConfigurations.default_context:
                context = None
            
            # get the config
            config = device_configurations.getConfig( context )
            # logging.error("ALL: " + str(device_configurations) )
            # logging.error("_SAVE: " + str(config._config[:5]))
            self.__save_config( hostname, config )

        return True
        
    
    def insert( self, hostname, device_config, user=None, rt=None, comment=None, commit=True ):
        """ ignore all optional fields (as we have no where to store them! unless we wnat to put them in a changelog file or something) """
        """ revision should be the datestamp for the file """

        # determine the contexts we care about
        contexts = device_config.getContexts()

        states = device_config.is_commit_up_to_date()
        person = None
        up_to_date = True
        for c in states:
            person = states[c]['by']
            if states[c]['up_to_date'] == False:
                raise ConfigurationStorageWarning, 'configuration has changed, but has not been saved by %s' % (person,) 

        # get the most recent configs
        logging.debug( "getting most recent config from disk for %s" % (hostname,))
        old_dc = self.get( hostname, contexts=contexts, ref_type=device_config )
        # logging.error("%s" % (old_dc))

        # the new config shoudl have todays date as revision
        rev = self._get_date()
        # 1) no config exists at all for this device
        if len( old_dc.getContexts() ) == 0:
            logging.debug( 'inserting new configuration')# + "\n" + str(device_config))
            if commit:
                self._save( hostname, device_config, revision=rev )
            return True, person, {}
            
        # 2) configuration already exists
        else:

            logging.debug("comparing new configuration last known")# + "\n" + str(device_config))
            # logging.error( "CHECK CHANGE:\n  old=" + str(old_dc._configs[0]._config[:5]) + "\nnew=" +str(device_config._configs[0]._config[:5]))

            # work out if new config is different
            # logging.debug("  old: %s" % (old_dc,))
            # logging.debug("  new: %s" % (device_config,))

            changed, diff = self.diff( old_dc, device_config, ignore_comments=True )
            logging.debug( "changed: %s, diff: %s" % (changed,diff) )
        
            if changed:
                if len( old_dc.getContexts() ) == 0:
                    logging.debug( '  inserting new configuration, revision %s' %(rev) )
                else:
                    logging.debug( '  inserting changed configuration, revision %s' %(rev) )
                if commit:
                    self._save( hostname, device_config, revision=rev )
                return True, person, diff
            else:
                logging.debug( '  no changes since last revision' )
                return False, person, {}

        # logging.debug('unknown insert error')
        return None, None, None


#######################################################################
# storage classes
#######################################################################

class NetConfigStorageException( Exception ):
    def __init__( self, value ):
        self.value = value
    def __str__( self ):
        return repr( self.value )
