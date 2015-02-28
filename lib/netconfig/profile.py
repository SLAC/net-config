from __future__ import with_statement

import logging
try:
    from yaml import load, dump
    try:
        from yaml import CLoader as Loader, CDumper as Dumper
    except ImportError:
        from yaml import Loader, Dumper
except:
    pass
from os import utime, path


class CacheException( Exception ):

    def __init__( self, value ):
        self.value = value
    
    def __str__( self ):
        return repr( self.value )



class Cache(object):
    """
    keeps a persistent lookup table on disk (as yaml config) of a device to the profile that should be used
    we also take care to scope the 'groups' that are used such that different groups may use different profiles for the same device
    """
    
    cache_file = None
    cache = {}
    default_group = 'default'
    
    def __init__( self, cache_file ):
        self.cache_file = cache_file
        self.cache = {}

    def store( self, hostname, profile_name, section=None ):
        """ stores the cache entry """
        if section == None:
            section = self.default_group
        logging.debug( "storing cache %s = %s in section %s" % (hostname,profile_name,section) )
        if not self.cache:
            self.cache = {}
        if not section in self.cache:
            self.cache[section] = {}
        self.cache[section][hostname] = profile_name
        
    def get( self, hostname, section=[] ):
        """ retrieves the appropriate profile for host """
        profile_name = None
        if isinstance( section, str ):
            section = [ section ]
        if len(section) == 0:
            section = [ self.default_group ]
        logging.debug('get profile: %s in %s' % (hostname,section))
        for s in section:
            # logging.debug(' section: %s / %s' %(s,self.cache))
            if s in self.cache:
                # logging.debug(' cached? %s\t%s' %(hostname in self.cache[s],self.cache[s],))
                if hostname in self.cache[s]:
                    profile_name = self.cache[s][hostname]
                    logging.debug("    found in section %s: %s" % (s,profile_name) )
            else:
                logging.debug( ' not found')
        # logging.debug("name: " + str(profile_name))
        return profile_name

    def _load(self):
        logging.debug( "  loading profile cache from " + self.cache_file )
        cache = {}
        try:
            cache = load( open(self.cache_file, 'r' ), Loader=Loader )
        except IOError,e:
            # new file?
            pass
        except Exception,e:
            logging.error("Error loading cache from disk: %s %s" % (type(e),e) )
        if not cache:
            cache = {}
        return cache
        
    def load( self ):
        """ load the file from disk """
        this = self._load()
        if not this == {}:
            self.cache = this
        else:
            logging.error("cache file did not contain useable data")
        

    def save( self, *hints ):
        """ reads in the cache from disk first and updates the changed data before writing to disk """

        # load the file from disk
        logging.debug( "checking profile cache from " + self.cache_file )

        # if the cache has changed, need to write back to it
        on_disk = self._load()
        # logging.debug("\nONDISK: %s\nCACHE: %s" % (on_disk,self.cache) )
        
        diff = False
        groups = list( set(on_disk.keys()+self.cache.keys()) )
        for g in groups:
            if not g in on_disk or not g in self.cache:
                diff = True
                break
            else:
                if not sorted(on_disk[g].keys()) == sorted(self.cache[g].keys()):
                    diff = True
                    break
                for k in self.cache[g].keys():
                    # logging.debug("k: %s: %s->%s" % (k,on_disk[g][k],self.cache[g][k]))
                    if not on_disk[g][k] == self.cache[g][k]:
                        diff = True
                        break
        
        if diff:
            logging.debug("profile cache has changed")
            # add stuff from disk
            for g in groups:
                try:
                    a = on_disk[g].items() if g in on_disk else {}
                    b = self.cache[g].items() if g in self.cache else {}
                    if len(hints):
                        for h in hints:
                            a[h] = self.cache[g][h]
                        self.cache[g] = a 
                    else:
                        d = dict( set(b) - set(a) )
                        for k,v in d.iteritems():
                            logging.debug(" %s %s " % (k,v))
                            self.cache[g][k] = v
                except Exception, e:
                    # in case of parsing errors etc
                    pass

            logging.debug("  saving profile cache to %s" % (self.cache_file,))    
            try:
                with open(self.cache_file,'w+') as stream:
                    dump( self.cache, stream, Dumper=Dumper)
                    # logging.debug("CACHE: %s" % (self.cache,))
            except Exception,e:
                logging.warn("profile cache save error: %s %s" % (type(e),e))
            
        return diff
