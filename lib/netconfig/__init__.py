import os
import ConfigParser
import multiprocessing
import types

from profile import Cache as ProfileCache
from Connector import *
from netconfig.drivers import IncompatibleDeviceException
from slac_utils.env import get_user
import util
import inspect
import importlib

try:
    from yaml import load, dump
    try:
        from yaml import CLoader as Loader, CDumper as Dumper
    except ImportError:
        from yaml import Loader, Dumper
except:
    pass

import logging
import traceback

#######################################################################
# REgister drivers
#######################################################################


def get_subsubclasses_for(klass):
    for cls in klass.__subclasses__():
        # logging.debug("  found: %s" % (cls,))
        yield cls
        if len(cls.__subclasses__()) > 0:
            # logging.debug("    has more children")
            for c in get_subsubclasses_for(cls):
                yield c
    return


#######################################################################
# Exceptions
#######################################################################

class NetConfigException( Exception ):
    def __init__( self, value ):
        self.value = value
    def __str__( self ):
        return repr( self.value )


#######################################################################
# Utility
#######################################################################


def config_file( file=None, env='NETCONFIG_CONF' ):
    if file == None:        
        if os.environ.has_key( env ):
            file = os.environ[env]
        else:
            raise Exception, 'no net-config configuration file defined (use filepath or environment variable \'' + str(env) + '\''
    # check file exists
    #logging.debug( "loading config file " + c)
    if os.path.exists( file ): return file
    else: raise Exception, 'net-config configuration file ' + str(file) + ' not found'


def parse_config( f ):
    cfg = None
    # if the arg is a file, then parse it, otherwise, accept as Conf object
    if isinstance( f, ConfigParser.SafeConfigParser ):
        cfg = f
    elif os.path.exists( f ):
        cfg = ConfigParser.SafeConfigParser()
        # logging.debug( "loading config parser object from file " + f )
        cfg.read( f )
    else:
        raise NetConfigException, 'unknown configuration type ' + str(f)
    return cfg
# 
# 
# def get_profile( profile_name, config ):
#     """ retrieves the appropriate section from the default profiles """
#     options = {}
#     if not config.has_section( profile_name ):
#         raise ConfigParser.NoSectionError( "%s does not exist in profiles" % (profile_name,))
# 
#     for k,v in config.items( profile_name ):
#         options[k] = v
#         #logging.debug( k + " " + v)
# 
#     return options

#######################################################################
# Main Class
#######################################################################

class NetConfig( object ):
    """ class to provide access to net-config stuff """
    
    # top level configuration section
    system_config_section_name = 'net-config'
    system_config = None
    
    # parameter pointing to the profile definitions
    profiles_config_name = 'profiles_file'
    profiles_config = None

    # parameter pointint to the lcoatin of the cache file of device -> profile maps
    profile_cache_name = 'profile_cache_file'
    profile_cache = None
    
    # parameter pointint to the lcoatin of the cache file of device -> profile maps
    firmware_name = 'latest_firmware'
    firmware_cache = None

    # mutex for profile writes
    mutex = None
        # 
    # def __init__( self, system_config ):
    #     
    #     self.mutex = multiprocessing.Lock()
    #     
    #     # logging.error("1: %s"%(system_config,))
    #     self.system_config = parse_config( system_config )
    # 
    #     # logging.error("2: %s"%(self.profiles_config_name,))
    #     self.profiles_config = self.get_config( self.profiles_config_name )
    # 
    #     # logging.error("3: %s"%(system_config,))
    # 
    #     # create the cache        
    #     self.profile_cache = Cache( self.system_config.get( self.system_config_section_name, self.profile_cache_name ) )
    #     self.reload_profile_cache()
    # 
    #     # get the firmware config
    #     self.firmware_cache = self.get_config( self.firmware_name )
    # 
    #     # keep a cache of the connected devices
    #     self.devices = []

    def get_config( self, section ):
        return parse_config( self.system_config.get( self.system_config_section_name, section ) )

    def __del__( self ):
        for d in self.devices:
            d.disconnect()
        self.save_profile_cache( *[ d.hostname for d in self.devices ] )
    
    def get_firmware_map( self ):
        """ retrieves the firmware cache"""
        config = self.firmware_cache
        firmware_map = {}
        for s in config.sections():
            firmware_map[s] = {}
            for o in config.options( s ):
                # logging.debug( "s: " + str(s) + ", o: " + str(o))
                firmware_map[s][o] = config.get( s, o )
        #logging.debug( "firmware map " + str(firmware_map) )
        return firmware_map

        
    def get_device_map( self ):
        """ in order to conduct relevant mapping of config files to the device_type, we need a dict of """
        # device_name: device_type
        # we do construct this here
        cache = self.profile_cache
        profiles = self.profiles_config

        data = {}
        for s in cache.cache.keys():
            for c in cache.cache[s]:
                # c == device name, p == profile type
                p = cache.get( c )
                # get device type
                try:
                    data[c] = profiles.get( p, 'device_type')
                except:
                    pass
        return data


    # def get_profile( self, profile_name, config ):
    #     """ retrieves the appropriate section from the default profiles """
    #     options = {}
    #     if not config.has_section( profile_name ):
    #         raise ConfigParser.NoSectionError( "%s does not exist in profiles" % (profile_name,))
    # 
    #     for k,v in config.items( profile_name ):
    #         options[k] = v
    #         #logging.debug( k + " " + v)
    # 
    #     # get username
    #     if not options.has_key( 'username' ):
    #         options['username'] = os.getenv('USER')
    # 
    #     return options


    def get_options( self, profile_config, profile_name, options={}, skip_options=( 'username', ) ):

        # get options fromt he profile
        profile = self.get_profile( profile_name, profile_config )

        # overwrite with command line args
        logging.debug( '  opts: %s -> %s' % (options,profile) )
        skip = [ i for i in skip_options ]
        # logging.debug("SKIP: %s" % (skip,))
        # if we force passwords in the porfile def, do not allow user defined passwords (eg with our asa's)
        if 'force_passwords' in profile and profile['force_passwords']:
            for p in ( 'password', 'enable_password' ):
                skip.append( p )
        for k in options:
            # don't overwrite profile defined usernames if exists
            # logging.debug(" k: %s \t(%s)" % (k,skip))
            if not k in skip:
                profile[k] = options[k]

        # convert following into ints
        for k in [ 'threads', 'login_timeout', 'command_timeout', 'long_command_timeout', 'probeable' ]:
            if profile.has_key(k):
                profile[k] = int(profile[k])

        # fill in passwords
        logging.debug("  final options: " + str(profile))
        profile = util.parsePasswords( profile, exclude=( 'force_passwords', ) )
        return profile


    # def get_device( self, device_type, host, profile ):
    #     # iterate through all the classes that inherit from Device and see if their name matches device_type
    #     for c in get_subsubclasses_for( Device ):
    #         # logging.debug("  checking class %s" % (c,))
    #         for i in ( 'port', 'enable_password', 'prime' ):
    #             if not i in profile:
    #                 profile[i] = None
    #         # logging.debug(">>>I: %s" % profile)
    #         # if not 'port' in profile:
    #         #     profile['port'] = None
    #         # if not 'enable_password' in profile:
    #         #     profile['enable_password'] = None
    #         logging.debug('creating device with profile: %s' % (self.redact_profile(profile),))
    #         device = c( host, profile['username'], profile['password'], profile['enable_password'], connector_type=profile['connector_type'], port=profile['port'], prime=profile['prime'] )
    #         if device.name == device_type:
    #             return device
    #     # failed
    #     raise Exception( "Device type '%s' not registered." % (device_type,))


    def redact_profile( self, profile ):
        debug_profile = {}
        for k, v in profile.iteritems():
            i = v
            if search( 'password', k ):
                i = '********'
            debug_profile[k] = i
        return debug_profile

    def _get_device( self, host, profile ):
        """ get the network device instance, using the cache """
        # create the obj based on the type
        logging.debug( "creating device driver for %s (type %s), with profile: %s" % (host, profile['device_type'], profile ) ) #self.redact_profile(profile) ) )
        
        # reset hostname and port if necessary
        if 'connector_hostname' in profile:
            host = profile['connector_hostname']
        port = None
        if 'port' in profile:
            port = profile['port']
        
        # create the device
        device = self.get_device( profile['device_type'], host, profile )
        self.devices.append( device )
        
        if 'prompt_output_wait' in profile:
            device.prompt.output_wait = float(profile['prompt_output_wait'])
        
        if 'connector_options' in profile:
            device.connector.options = profile['connector_options']
        if 'login_timeout' in profile:
            device.connector.timeout = profile['login_timeout']
        
        # set the firmware maps
        if self.firmware_cache:
            device.system.firmware.firmware_map = self.get_firmware_map()
        
        return device

    def probe_device( self, hostname, profile ):
        """ will attempt to try all network device drivers and connector types to connect to host """
        # device_class = get_class( profile['device_type'] )
        logging.debug( "probing %s with profile %s" % (hostname, self.redact_profile(profile) ) )

        # get the network_device object
        network_device = self.get_device( profile['device_type'], hostname, profile )

        # set connector options
        if network_device.connector.options == None:
            network_device.connector.options = {}
        if 'connector_options' in profile:
            network_device.connector.options = profile['connector_options']

        # attempt to connect
        okay = True
        try:
            
            # logging.error("OPTS: %s (%s)" % (network_device.connector.options, profile['connector_options']))
            # just attempt to login
            if 'login_timeout' in profile:
                network_device.connect( timeout=profile['login_timeout'] ) #, **network_device.connector.options )
            else:
#                network_device.connect( **network_device.connector.options )
                network_device.connect() # **network_device.connector.options )

            # attempt to gain enable mode
            network_device.priviledge_check()

        # these all mean that this driver probably disn't correct
        except AccessException, e:
            okay = False
        except TimeoutException, e:
            okay = False
        except IncompatibleDeviceException, e:
            # logging.error("incompatible driver: %s" % (e,))
            okay = False
        except NotImplementedError, e:
            okay = False
        except NetworkException, e:
            # propogate issue up
            network_device.disconnect()
            raise e
        except RemoteException, e:
            # man in middle
            network_device.disconnect()
            raise e
        except ConnectorException, e:
            okay = False
        except Exception, e:
            # propogate error up
            network_device.disconnect()
            # logging.debug("ERROR Here: %s %s" % (type(e),e))
            raise NetConfigException( str(e) )

        network_device.disconnect()
        if not okay:
            logging.debug( 'probing %s with profile %s failed: (%s) %s' %(hostname,self.redact_profile(profile),type(e),e) )
            return False
        return True

    # def profiles( self, glob=None ):
    #     """ retrieve a list of profiles configured """
    #     profiles = []
    #     for p in self.profiles_config.sections():
    #         # logging.debug("  found profile %s" % (p,))
    #         if glob == None:
    #             profiles.append( str(p) )
    #         else:
    #             m = search( glob, p )
    #             if m:
    #                 profiles.append( str(p) )
    #     return profiles


    def post_process_profile( self, profile, user=None ):
        if not user == None and not 'username' in profile:
            profile['username'] = user
        if not 'username' in profile or profile['username'] == None:
            profile['username'] = get_user( fqdn=False )
        return profile

    def attempt_device_discover( self, host, options={}, profiles=[], user=None ):
        """ iterates through all of the profiles and attempt to connect to device """
        for profile_name in profiles:
            logging.debug( "attempting profile %s for %s" %( profile_name, host ) )
            #  limit
            profile = self.post_process_profile( self.get_options( self.profiles_config, profile_name, options=options ), user=user )
            # logging.error("USER: profile %s, kwargs %s, options %s" % (profile, user, options))
            if 'probeable' in profile and profile['probeable']:
                success = self.probe_device( host, profile )
                if success == True:
                    logging.debug( " found successful profile " + profile_name )
                    return profile_name, profile
            else:
                logging.debug("  skipping as not probeable")
        raise NetConfigException, "could not discover profile"
    
    def get( self, host, options={}, profiles=[], user=None, use_cache=True, section_map={} ):
        """
        iterate through the list of profiles and determine which one matches for host 
        if profiles is defined, then it only allows using the defined list of profiles
        section map key=profile_name, vaulue=section to store under cache
        """
        # check cache
        host = host.lower()
        profile_name = None
        profile = None
        probe_string = 'auto'
        probing = False

        section = None
        
        logging.debug("get cache for network device %s (cache %s), profiles: %s, options: %s" % (host,use_cache, profiles,options))
        if use_cache:
            try:
                section = [ v for i,v in section_map.iteritems() ]
                if len(section) == 0 and 'cache_group' in options:
                    section = options['cache_group']
                # logging.debug("SECTION: %s" % (section,))
                profile_name = self.profile_cache.get( host, section=section )
                logging.debug(" found profile_name %s in section %s" % (profile_name,section))
                if profile_name:
                    try:
                        self.mutex.acquire()
                        profile = self.get_profile( profile_name, self.profiles_config ) 
                        probing = False
                        logging.debug("  found profile %s" % (profile,))
                    finally:
                        self.mutex.release()
            # except ConfigParser.NoSectionError, e:
            #     #logging.warn("profile " + str(profile_name) + " does not exist")
            #     profile_name = None
            #     profile = {}
            except Exception, e:
                logging.error("TODO profile failure %s: %s" % (type(e),e))

        # see if we're forcing a profile within the above subset of profile defs
        # logging.error("PROFILE: %s" % (options['profile'],))
        if 'profile' in options and options['profile']:
            if not options['profile'] == probe_string:
                profile_name = options['profile']
                logging.debug( "forced using profile: %s" % (profile_name,) )
            elif options['profile'] == probe_string:
                probing = True

        # username
        if user:
            options['username'] = user

        # try to get the profile
        try:
            profile = self.get_options( self.profiles_config, profile_name, options )
        except Exception,e:
            logging.debug("  get profile options failed %s %s" % (type(e),e))
            probing = True

        # attempt a probe if necessary
        if probing:
            if len(profiles) == 0:
                profiles = self.profiles()
            logging.debug("probing for profile using %s" % (profiles))
            profile_name, profile = self.attempt_device_discover( host, options=options, profiles=profiles, user=user )

        # set username
        if not 'username' in profile and not user == None:
            profile['username'] = user
        else:
            if not profile.has_key( 'username' ):
                profile['username'] = os.getenv('USER')

        if profile_name == None:
            raise NetConfigException( "profile probing failed" )

        if use_cache:
            this_section = None
            if profile_name in section_map and section_map[profile_name]:
                this_section = section_map[profile_name]
            elif section:
                this_section = section
            logging.debug("saving to cache: %s section %s, profile %s (map %s)" % (host, this_section,profile_name,section_map))
            self.profile_cache.store( host, profile_name, section=this_section )
            self.save_profile_cache( host )

        return self._get_device( host, profile )
    
    def connect( self, device, login_timeout=None, connector_options={}, prime=None, **kwargs ):
        """ wrapper to connect to the device supplied with the options """
        # specific user
        # if 'user' in options:
        #     connector_options['user'] = options['user']

        # connect to device
        logging.debug("connect options: %s" %(connector_options,))
        if connector_options == None:
            connector_options = {}
        return device.connect( timeout=login_timeout, prime=prime, **connector_options )

    def reload_profile_cache( self ):
        """ reload profile cache """
        self.profile_cache.load()
        
    def save_profile_cache( self, *hints ):
        """ saves the profile cache """
        if not self.profile_cache == None:
            self.mutex.acquire()
            try:
                # logging.error("saving...")
                self.profile_cache.save( *hints )
                # logging.error("done")
            except:
                pass
            finally:
                self.mutex.release()
        
    def get_profile_cache( self ):
        return self.profile_cache


#######################################################################
# new api
#######################################################################

def camel_to_underscore(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def underscore_to_camel(name):
    s1 = [ i.title() for i in name.split('_') ]
    return ''.join(s1)

class NewNetConfig( NetConfig ):
    """
    factory class to access network devices
    """
    
    def __init__( self, config=None, mutex=multiprocessing.Lock() ):
        
        self.mutex = mutex
        
        # if no config, try to determine relative to path
        
        f = open(config,'r')
        self.config = load( f, Loader=Loader )
        # logging.debug("CONFIG: %s -> %s" % (config,self.config))
        self.profiles_config = self.config

        if not 'profiles' in self.config:
            raise SyntaxError, 'no profiles defined in configuration file!'
        if not 'profile_cache' in self.config:
            raise SyntaxError, 'no profile cache defined in configuration file!'
        
        # create the cache        
        self.profile_cache = ProfileCache( self.config['profile_cache'] )
        self.reload_profile_cache()

        # keep a cache of the connected devices
        self.devices = []
    

    def get_device( self, device_type, host, profile ):
        """
        given the type, determine the relevant driver class to load and create new object
        """
        # iterate through all the classes that inherit from Device and see if their name matches device_type
        try:
            m = 'netconfig.drivers.' + device_type
            # logging.debug("module path: %s" % (m,))
            module = importlib.import_module( m )
            # logging.debug("module: %s" % (module,))
            klass = underscore_to_camel( device_type )
            # logging.warn("LOOKING FOR %s -> %s (%s)" % (device_type,klass, profile))
            c = getattr( module, klass )
            # TODO check inheritence of object == Device
            for i in ( 'port', 'enable_password', 'prime' ):
                if not i in profile:
                    profile[i] = None
            # logging.debug("I: %s" % profile)
            return c( hostname=host, **profile )
        
        except Exception,e:
            logging.error("%s %s: %s" % (type(e),e, traceback.format_exc() ))
    
        raise Exception( "Device type '%s' is not registered" % (device_type,))

    def get_profile( self, profile_name, config ):
        """ retrieves the appropriate section from the default profiles """
        options = {}
        # logging.debug('getting profile %s' % (profile_name,))
        if profile_name and not profile_name in config['profiles']:
            s = "%s does not exist in profiles" % (profile_name,)
            logging.warn( s )
            raise SyntaxError, s

        for k,v in config['profiles'][profile_name].iteritems():
            options[k] = v

        logging.debug("profile definitions for %s: %s" % (profile_name,options,))
        return options


    def profiles( self, glob=None ):
        """ retrieve a list of profiles configured """
        profiles = []
        for p in self.config['profiles'].keys():
            # logging.debug("  found profile %s" % (p,))
            if glob == None:
                profiles.append( str(p) )
            else:
                m = search( glob, p )
                if m:
                    profiles.append( str(p) )
        return profiles
        
        
