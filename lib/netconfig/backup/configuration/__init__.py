import logging
import difflib
import re
import dateutil.parser
import tarfile
import tempfile
from shutil import rmtree
import os.path
import filecmp
from subprocess import Popen, PIPE
from pprint import pformat

from slac_utils.klasses import create_klass, path_of_module, modules_in_path
from slac_utils.string import camel_case_to_underscore


"""
A class to hold a configuration
"""


class Configuration( object ):
    """ holds a configuration object """
    
    for_component = None
    
    # store the configuration as an array
    _config = None
    # store the name of the applicable context
    _context = None
    # store the known revision of this configuration
    _revision = None
    
    working_dir = None
    
    # for determining if a line is within a stanza or not (for contextual diffs)
    stanza_prefix = r'^\s+'

    comment_matches = []
    
    scrub_matches = []
    scrub_string = '********'
    
    def __init__( self, *args ):
        self._config = None
        self._context = None
        self._revision = None
        self.working_dir = None
        if len( args ) == 1:
            logging.debug("setting from init " + str(args[0]))
            self.set( args[0] )

    def set( self, array ):
        # if it's a file, then load it first
        if type(array) == str and os.path.isfile( array ):
            logging.debug("creating config from file " + str(array) )
            f = open( array, 'r' )
            # self._config = f.read()
            self._config = []
            for l in f.readlines():
                # logging.error("L " + str(l))
                l = l.rstrip()
                self._config.append( l )
        else:
            # logging.debug("creating from text input " + str(array))
            self._config = array
    
    def _get( self, ignore_meta=False, ignore_lines=[] ):
        # remove the comment lines for comparision
        p = None
        if ignore_meta:
            meta_lines, a, x, p = self.get_comment_line_info()
            ignore_lines = sorted(meta_lines, reverse=True)
        logging.debug("comment lines=%s: %s, by=%s" %(ignore_meta,ignore_lines,p))
        n = 0
        for l in self._config:
            if not n in ignore_lines:
                yield l
            n = n + 1
        return
    
    def get( self, ignore_meta=False, ignore_lines=[] ):
        return [ i for i in self._get( ignore_meta=ignore_meta, ignore_lines=ignore_lines ) ]
        
    def setContext( self, string ):
        self._context = string

    def getContext( self ):
        return self._context


    def set_revision( self, string ):
        self._revision = string

    def get_revision( self ):
        return self._revision

    def __str__( self ):
        this_str = ''
        for l in self._config:
            this_str = this_str + l +'\n'
        return this_str

    def __cmp__( self, configuration ):
        """ compares against another configuration """
        # TODO: deal with the comment lines
        return cmp( str(self), str(configuration) )

    def diff( self, configuration, ignore_comments=False ):
        this_config = [ i for i in self.get( ignore_meta=ignore_comments ) ]
        that_config = [ i for i in configuration.get( ignore_meta=ignore_comments ) ]
        ret = []
        for l in difflib.unified_diff( this_config, that_config ):
            ret.append( str(l) )
        return ret

    def config_block( self, lines, start, size, n=3 ):
        """ read the lines from the config, and see if there is an indent of some sort so we spit out the whole stanza """
        if len(lines) == 0:
            # return [], start, start+size
            return [], 0, 0

        # as the start may be in a previous block, we walk down until we have the first diff line, then we start 
        # analysis from there            
        i = start + n - 1
        # initial setup for if lines are at start of config (ie start < n)
        # if start < n:
        #     logging.debug("initial line search")
        #     i = 0
        #     for x in xrange( 0, n ):
        #         logging.debug("  (%s) %s'" % (i,lines[x]) )
        #         if re.match( '^ ', lines[x]):
        #             logging.debug("   found empty")
        #             i = i + 1
        #     i = i + 1 # get next line

        logging.debug(' block: start=%s, i=%s, n=%s, size=%s' % (start,i,n,size) )
        
        # in case we're near the end
        if i > len(lines) - 1:
            i = len(lines) - 1

        # general work flow:
        #  take the start line, and check if it's indented
        #  if it is, then check to see if the diff'd lines are part of the previous block or not (by shear virtue of the fact that if it is, then there will only be 3 lines in), reset start to real block
        #  work backwards to ensure we are within a single indent code block
        #  work forwards to ensure we have the full code block

        logging.debug("  trying to find initial start line: %s = %s" % (i,lines[i]) )
        in_stanza = False
        
        # are we close to the end block? count number of lines til end; if this count is <= n, then we actually want the next block, not htis one
        if not self.stanza_prefix == None:

            # are we inside a previous block?
            previous_block = False

            # work down to see if i < n
            logging.debug("    determine if diff is part of previous block")
            c = i
            while c < start+size:
                logging.debug('     (%s) %s' % (c,lines[c]) )
                if not re.match( self.stanza_prefix, lines[c] ):
                    previous_block = True
                    logging.debug("    inside another block!")
                    break
                c = c + 1

            logging.debug( "   c: %s, m: %s, n: %s" % (c,c-i-1,n))
            if previous_block and c-i-1 >= n:
                start = c + 1
                in_stanza = False
                logging.debug("    inside previous block: resetting to (%s) %s" % (start,lines[start]))

            else:
                logging.debug("    working backwards to find stanza")
                while re.match( self.stanza_prefix, lines[i] ):
                    logging.debug('     (%s) %s ' % (i,lines[i]) )
                    in_stanza = True
                    i = i - 1
                    if i == 0:
                        break
        
        # we test this by walking down from this 'start' n times to determine if we exit and reenter into another stanza
        if in_stanza:
            start = i
        logging.debug("    found real start line: (%s) %s, instanza=%s" % (start,lines[start],in_stanza) )
        
        # the end may be in another stanza, so we start from the real start line, and determine if that's within a stanza or no
        end = start + 1
        # if not a stanza, then encap all 
        if not in_stanza:
            end = start + size
        if end >= len(lines):
            end = len(lines) - 1
        # logging.debug("END: " + str(end) + '/ ' + str(len(lines)))
        # try to no analyse the end that is before the start
        logging.debug("  trying to find initial end line: (%s) %s" % (end,lines[end]) )
        in_stanza = False
        if not self.stanza_prefix == None:
            while end < len(lines):
                logging.debug('     (%s) %s' % (end,lines[end]) )
                if re.match( self.stanza_prefix, lines[end] ):
                    in_stanza = True
                    end = end + 1
                else:
                    break
        if not in_stanza:
            logging.debug( '  end block not found')
            end = start + size - 1
        
        end = end - 1

        # don't go past
        logging.debug("  set threshold: %s %s" % (end, len(lines)))        
        # end of file...
        if end >= len(lines):
            end = len(lines) - 1
            
        logging.debug("    found real end line (%s): %s " % (end,lines[end]) )
        data = lines[start:end+1]
        logging.debug("found block: start %s, end %s" %(start,end) )
        # for s in data:
        #     logging.debug(" %s" % (s,))
            
        return data, start, end


    def get_diff_line_range( self, line ):
        m = re.match( r'@@ (\+|\-)?(?P<before_line>\d+),(?P<before_size>\d+) (\+|\-)?(?P<after_line>\d+),(?P<after_size>\d+) @@', line )
        if m:
            a, z1 = m.group( 'before_line', 'before_size')
            b, z2 = m.group( 'after_line', 'after_size')
            # use index of 0, not one for our analysis as our array starts from 0
            return int(a)-1, int(z1), int(b)-1, int(z2)
        return None, None, None, None

    def contextual_diff( self, configuration, ignore_comments=False ):
        """ work out a context for the diff based on stanzas """
        # ignore_comments = False
        logging.debug("determining diffs without comments=" + str(ignore_comments))
        # TODO: better to get full configs and work out which are comments after doing the diffs?
        this_config = [ i for i in self.get( ignore_meta=ignore_comments ) ]
        that_config = [ i for i in configuration.get( ignore_meta=ignore_comments ) ]

        # do a standard diff, and analyse the lines that it says there's differences between
        # logging.debug("diffing... %s %s" % (this_config, that_config))
        diffs_found = []
        this_diff = None
        diffs = {}
        for l in difflib.unified_diff( this_config, that_config ):
            if re.match( r'@@ (?P<lines>.*) @@', l ):
                diffs_found.append( l )
                this_diff = l
            if not this_diff in diffs:
                diffs[this_diff] = []
            diffs[this_diff].append( l.strip() )
            # logging.debug('  %s' % (l.strip(),))        
                
        # determine the enclosing blocks from this and that config, and do a diff from those blocks
        # if no blocks are really found, then use what diff found
        data = []
        range_end = None
        for d in diffs_found:
            logging.debug('=================== '+str(d.rstrip())+ '=========================')
            a, z1, b, z2 = self.get_diff_line_range( d )
            logging.debug("  a: %s, z1: %s, b: %s, z2: %s" % (a,z1,b,z2) )
            # for s in diffs[d]:
            #     logging.debug(" %s" % (s,))

            if not range_end == None:
                # this overlaps the last analysis, skip
                if b < range_end - 1:
                    logging.debug("skipping ( b="+str(b)+"<"+str(range_end-1)+")")
                    continue

            # determine blocks that this diff is for
            logging.debug("this block:")
            this, this_start, this_end = self.config_block( this_config, a, z1 )
            logging.debug("that block:")
            that, that_start, that_end = self.config_block( that_config, b, z2 )

            # set end point for this for next consideration
            range_end = that_end
            
            # determine the actual diff from these blocks
            # diff = self.scrub( [ i for i in difflib.unified_diff( this, that, n=50 ) ][3:] )
            diff = [ i for i in difflib.unified_diff( this, that, n=50 ) ][3:]

            # for instance where we have previous block data in the diff, we may have suplurflous diff lines at the end, so we remove them here
            logging.debug('removing superfluous diff data:')
            c = 0
            for i in xrange( len(diff)-1, 0, -1 ):
                # need initial space because of diff prefix
                s = ' '
                if self.stanza_prefix:
                    s = s + str(self.stanza_prefix)
                if re.match( s, diff[i] ):
                    c = c + 1
                    logging.debug( " %s" % (diff.pop(-1),) )
                else:
                    break
                    
            # determine the diff unified info that we should use
            # meta = '@@ -' + str(this_start) + ',' + str(len(this)) + ' +' + str(that_start) + ',' + str(len(that)) + " @@"
            meta = '@@ -%s,%s +%s,%s @@' % (this_start,len(this)-c,that_start,len(that)-c)
            data.append( { 'diff': diff, 'meta': meta } )
            logging.debug("diff: %s" % (meta,))
            # for i in diff:
            #     logging.debug("%s" % (i,))

        return data

    def get_comment_line_info( self ):
        """ determines the line numbers which correspond to the configuration update/saved comments; not it counts from 0 """
        array = []
        last_change = None
        last_save = None
        by = None
        logging.debug( "determining comment lines in config" )
        meta = {}
        for i in xrange( 0, len(self._config) ):
            found = False
            for m in self.comment_matches:
                if found == False:
                    this = re.search( m, self._config[i] )
                    if this:
                        # logging.debug( "  %s\t%s" % (m,self._config[i]) )
                        g = this.groupdict()
                        meta.update( g )
                        array.append( i )
                        found = True
                if found == True:
                    continue

        # logging.debug('  comment meta %s' % (meta,))
        if 'last_change' in meta:
            last_change = self._convertDate(meta['last_change'])
        if 'last_save' in meta:
            last_save = self._convertDate(meta['last_save'])
        # who's to blame?
        # logging.error("META: %s" % meta)
        by = None
        if 'save_user' in meta:
            by = meta['save_user']
        if last_change and last_save and last_change > last_save:
            if 'change_user' in meta:
                by = meta['change_user']
        logging.debug("  comment lines=%s, changed=%s, save=%s, by=%s"%(array,last_change,last_save,by) )
        # line index of comments, last changed, last saved, person saved
        return array, last_change, last_save, by
        
    def is_commit_up_to_date( self ):
        """ is the configuration saved in nvram upto date to that in memory? """
        a, change, save, person = self.get_comment_line_info( )
        if change > save:
            return False
        return True

    def _convertDate( self, string ):
        """ converts the datetime format in config to datetime object """
        dt = dateutil.parser.parse( string )
        return dt

    def scrub( self, block ):
        """
        given an array of strings, will remove sensitive information like passwords etc from output
        """
        # if no scrubs, then merge all
        # logging.error("LOCALS %s" % (locals()['CiscoIOSConfiguration']))
        # if len( self.scrub_matches ) == 0:
        #     # for c in ( CiscoIOSConfiguration, CiscoIOSWirelessConfiguration, CiscoCATOSConfiguration, CiscoTopSpinConfiguration, CiscoASAConfiguration ):
        #     for c in ( 'CiscoIOSConfiguration', 'CiscoIOSWirelessConfiguration', 'CiscoCATOSConfiguration', 'CiscoTopSpinConfiguration', 'CiscoASAConfiguration' ):
        #         klass = getattr(locals(),c)()
        #         logging.error("IN: %s" % (klass,))
        #         for s in klass.scrub_matches:
        #             logging.info("S: %s" % (s,))
        #             # self.scrub_matches.append( s )
                    
        # logging.error("MATCHES: %s" % ( self.scrub_matches, ) )
        for i in xrange( 0, len(block) ):
            # logging.info( "LINE: %s" % (block[i]))
            for m in self.scrub_matches:
                this = re.search( m, block[i] )
                if this:
                    block[i] = block[i].replace( str(this.group('redact')), str(self.scrub_string) )
                    continue
        return block



class DeviceConfigurations( object ):
    """
    a full description of a device backup
    """
    # lets keep a dict of the configs for each context
    _configs = []
    
    default_context = 'system'
    
    
    def __init__( self ):
        self._configs = []
    
    def getContexts( self ):
        """ returns the list of contexts of configs """
        contexts = []
        for i in self._configs:
            c = i.getContext()
            contexts.append( c )
        return contexts

    def getConfig( self, context=None ):
        """ get the configuration object for the context give, if None, return the system one """
        if context == None:
            context = self.default_context
        # check for the object
        for c in self._configs:
            this_context = c.getContext()
            if this_context == context:
                # logging.error('GETCONFIG: ' + str(c) )
                return c
        # return none if not there
        return None    
    
    def _setConfig( self, config_object ):
        """ inserts into config objects """
        # just keep it in a dict
        self._configs.append( config_object )
        return True

    
    def setConfig( self, item, config_type=None, context=None ):
        """ stores the config object for the context """
        # crate the configuration object based on the profile device_type
        # logging.error("SET CONFIG: %s" % (config_type,))
        c = self.get_config_obj( config_type )()
        # logging.error("C: %s" % (type(c),))
        c.set( item )
        # set the context
        if context == None:
            context = self.default_context
        c.setContext( context )
        #logging.error( "SET: " + str(c) + "\n cont " + context)
        # put it in it's collection
        self.append( c )

        return True
    
    def get_config_obj( self, config_component ):
        # map the name of the component to a module to import
        if isinstance( config_component, str ):
            name = config_component
        else:
            name = config_component.__class__.__name__.replace('Config','')
        config_klass = 'netconfig.backup.configuration.' + camel_case_to_underscore( name ) + '.' + name
        logging.debug("getting configuration object matched for %s -> %s" % (type(config_component),config_klass) )
        try:
            k = create_klass( config_klass )
            logging.debug("  created: %s" % (k,))
            return k
        except:
            raise SyntaxError, 'could not determine configuration object for ' + str(config_component)
 
    def set_config( self, item, obj, context=None ):
        c = self.get_config_obj( obj )()
        c.set( item )
        if context == None:
            context = self.default_context
        c.setContext( context )
        self.append( c )
        return True
    
    def append( self, configuration_object, force=False ):
        """ add the config to the device configs; forcing the replacement of a config with teh same context if requested """
        context = configuration_object.getContext()
        
        # if no context on the config, set to the default
        if context == None:
            configuration_object.setContext( self.default_context )
            context = configuration_object.getContext()
            
        # make sure context doesn't already exist
        contexts = self.getContexts()
        for c in contexts:
            #logging.error( "C: " + str(c) + ", CONT: " + str(context))
            if c == context:
                if not force:
                    raise  DeviceConfigurationsException, 'context ' + context + ' already exists'
        
        return self._setConfig( configuration_object )


    def __str__(self):
        string = ''
        for c in self.getContexts():
            #print '-----------------------------------------------------------------------''
            string = c + "\n"
            string = string + '-----------------------------------------------------------------------' + "\n"
            
            string = string + str(self.getConfig( context=c ))
        if len(self.getContexts()) == 0:
            string = '<empty device configuration>'

        return string
    
    
    def _cmpContexts( self, another_device_configurations ):
        """ cmps for contexts between itself and aother dc """
        # check contexts
        contexts = {}
        for i in self.getContexts():
            contexts[i] = 1
        
        if another_device_configurations:
            for j in another_device_configurations.getContexts():
                if contexts.has_key(j):
                    contexts[j] = contexts[j] - 1
                else:
                    return -1
                
        for k in contexts:
            if not contexts[k] == 0:
                return 1
        
        return 0
    
    def __cmp__( self, another_device_configurations ):
        """ diffs between the two device configurations objects """
        
        # store a tally of how different the configuration objects are
        diff_value = 0
        
        # make sure we have same contexts
        ret = self._cmpContexts( another_device_configurations )
        if ret == 0:
            # for each context, compare the configurations
            for c in self.getContexts():
                # logging.error( "CONTEXT: " + str(c) )
                this_config = self.getConfig( context=c )
                that_config = another_device_configurations.getConfig( context=c )
                this = cmp(this_config, that_config)
                diff_value = diff_value + this
        else:
            # TODO: is this correct?
            return -1
        
        # return which is more different based on cmp output
        return diff_value

    def diff( self, another_device_configurations, contexts=[], ignore_comments=True, scrub=True ):
        """ returns a dict of each context with it's diff (None) as an array of lines if no dict entry """
        diff = {}
        
        # logging.debug("DC self: %s, other: %s" % (self, another_device_configurations ))
        # TODO: need to determine proper way of determine valid contexts if changed
        if len(contexts) == 0:
            contexts = self.getContexts()
            # logging.debug("  contexts: %s" % (contexts,))

        for c in contexts:
            logging.debug("diffing context: %s" % (c,))
            this_conf = self.getConfig( context=c )
            that_conf = another_device_configurations.getConfig( context=c )
            # logging.debug("ANOTHER %s -> %s" %(self._configs[0],another_device_configurations._configs[0]))
            # str(another_device_configurations._configs[0]._config))

            logging.debug("  this: %s" % (type(this_conf),) )
            logging.debug("  that: %s" % (type(that_conf),) )

            # this has nothing; fake it so we don't have a None object
            if type(this_conf) == None:
                logging.debug("reseting THIS")
                this_conf = Configuration( '' )
            # if that_conf == None:
            #     logging.error("reseting THAT")
            #     that_conf = Configuration( '' )

            # logging.debug("  this: %s" % (this_conf,) )
            # logging.debug("  that: %s" % (that_conf,) )
    
            # logging.error("ABOUT TO DIFF CONF: " + str( type(this_conf) ) + " to " + str( type(that_conf) ) )
            diffs = this_conf.contextual_diff( that_conf, ignore_comments=ignore_comments )
            logging.debug( pformat(diffs) )
            for d in diffs:
                # logging.error("DIFF: %s" % (d))
                d['diff'] = that_conf.scrub( d['diff'] )
            if len(diffs) > 0:
                diff[c] = diffs
        # logging.error("DIFF FOR CONTEXT: " + c + "\n" + str(diff[c]))
        return diff
        
    def is_commit_up_to_date( self, contexts=[] ):
        """ determines if the contexts provided need to be saved """
        if len(contexts) == 0:
            contexts = self.getContexts()
        
        context_states = {}
        
        for c in contexts:
            lines, changed, saved, person = self.getConfig( c ).get_comment_line_info()
            # logging.warn("CHANGED: %s, SAVED: %s" % (changed,saved))
            context_states[c] = {
                'up_to_date': True,
                'by':   person,
            }
            logging.debug("  changed %s, saved %s" % (changed, saved))
            if not changed == None and not saved == None:
                if changed > saved:
                    context_states[c]['up_to_date'] = False
            elif saved == None and not person == None:
                context_states[c]['up_to_date'] = False
        return context_states


def all_config_klasses():
    p = os.path.dirname( path_of_module( Configuration ) )
    for m, mp in modules_in_path( p ):
        yield m
