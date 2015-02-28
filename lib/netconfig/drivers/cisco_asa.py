from netconfig.drivers.cisco_ios import PromptCiscoIos, ModelCiscoIos, RoutesCisco
from netconfig.drivers import MultipleFileConfig, Users, System, Device, Layer3, Arps, IncompatibleDeviceException

from netconfig.backup.configuration import DeviceConfigurations
from re import search, match, compile

import logging

#######################################################################
# Cisco ASA Firewall
#######################################################################

class PromptCiscoAsa( PromptCiscoIos ):

    mode = {
        'exec'      : '\> $',
        'enable'    : '\# $',
        'config'    : '\(config\)# $',
    }
    
    error = {
        'input': "Invalid input detected at",
        'incomplete': "Incomplete command.",
        'denied': 'Access denied.$|Invalid password',
    }
    
    interact = {
        'username': 'Username: $',
        'enable_password': '(P|p)assword: $',
        'question'  : "\[.*\]\? $",
        'pager': '\<\-\-\- More \-\-\-\>$'
    }
        
    interaction_keys = {
        'carriage_return': "\x0d",
        'pager': "\x20",
    }

    timeouts = {
        'login': 5,
        'short': 5,
        'medium': 15,
        'long': 60,
        'very_long': 600,
    }

    context_regex = r'(?P<preamble>(\w|\-)+)\/?(?P<context>\w+)?$'
    context_any = '.*'
    master_context = 'system'

    def terminal_buffer( self, size=0 ):
        return self.ask( 'terminal pager ' + str(size), cursor=self.cursor("mode","enable") )

    def cursor( self, mode, type=None, context=None ):
        # asa's system context is the same as no context
        if context == None:
            context = self.current_context
        return super( PromptCiscoAsa, self ).cursor( mode, type=type, context=context )


    def generate_prompt(self, preamble=None, mode=None, type=None, symbol=None, context=None, current=True ):
        s = symbol
        # logging.debug("GENERATE: preamble %s, mode %s, type %s, symbol %s, context %s / current %s, current %s" % (preamble,mode, type,symbol, context, self.current_context,current))
        done = False
        if mode == 'mode':
            if context == None:
                if current and self.current_context:
                    s = '/' + self.current_context + symbol
                else:
                    s = '%s%s' % (preamble if preamble else '',symbol)
                    done = True
            else:
                s = '/' + context + symbol
            if not done and not preamble == None:
                s = preamble + s
        # logging.debug("  S: %s" % (s,))
        return s

    def change_to_context( self, context ):
        # regenerate what we should expect with the chagne to the new context
        logging.debug("changing context to %s" % context )
        # self.setup_prompts( context=None, preamble=self.preamble, append_generic=True )
        self.setup_prompts( context=None, preamble='', current=False )
        ret = self.ask( 'changeto context %s' % (context,), output_wait=0.1 )
        logging.debug("change to context %s: %s" % (context,ret))
        # rediscover prompts?
        ok = self.discover_prompt()
        return ret
    
    def mode_enable( self ):
        logging.debug('asa attempting to get into enable mode from ' + str(self.current_cursor))
        n = 5
        try_using_login = True
        while n > 0:
            m, t, c = self.inverse_cursor( self.current_cursor )
            # logging.error("M: %s, T: %s, C: %s (want %s)" % (m,t,c,''))
            if m == 'mode':
                if t == 'exec':
                    cmd = 'login'
                    if not try_using_login:
                        cmd = 'enable'
                    res = self.ask( cmd, preempt=False )
                    logging.debug("exec command: %s" % (res,) )
                elif t == 'enable':
                    return True
            elif m == 'interact':
                if t == 'enable_password':
                    p = self.connector.password
                    if not try_using_login:
                        p = self.connector.enable_password
                    logging.debug("ENTERING PASSWORD")
                    res = self.ask( p, preempt=False, suppress_command_output=True )
                elif t == 'username':
                    res = self.ask( self.connector.user, preempt=False )
                logging.debug("interact command: %s" % (res,))
            elif m == 'error':
                if t == 'denied':
                    # let's try using the enable password instead
                    if try_using_login:
                        try_using_login = True
                    else:
                        logging.error("access denied")                    
                        return False
            else:
                logging.debug('  trying to move to ' + self.cursor('mode','enable') + ' from current prompt ' + self.current_cursor)
            n = n - 1
        logging.warn("dunno how to change from current prompt " + str(self.current_cursor) + ' to mode enable')
        return False
    
    def list_contexts( self, fail_okay=True ):
        contexts = []
        if self.change_to_context( self.master_context ):
            for l in self.tell( 'show context', cursor=self.cursor('mode','enable') ):
                m = []
                if m.append( search( r'^(\*| )(\w+)\s+.*$', l ) ) or m[-1]:
                    #logging.debug( "> " + m[-1].group(1) + ", " + m[-1].group(2) )
                    contexts.append( m[-1].group(2) )
            # contexts.append( 'system' )
        logging.debug("list found contexts " + str(contexts))
        return contexts


class ConfigCiscoAsa( MultipleFileConfig ):

    def list_files( self, re ):
        files = []
        d = compile( r'^Directory of (?P<dir>[a-z0-9]+\:\/.*$)' )
        f = compile( r'.*\s+\d{4}\s+(?P<file>(\w|\_|\.)+\.xml)$')
        this_directory = ""
        try:
            for l in self.prompt.tell( 'dir /recursive', cursor=[ self.prompt.cursor('mode','enable') ] ):
                # logging.debug("> " + str(l))
                m = []
                if m.append( d.search(l) ) or m[-1]:
                    this_directory = str(m[-1].group('dir'))
                    # remove stars
                    this_directory = this_directory.replace( r"/*", "" )
                    logging.debug("    found directory: " + this_directory )
                elif m.append( f.search(l) ) or m[-1]:
                    this = m[-1].group('file')
                    fp = this_directory + '/' + this
                    logging.debug("     found file: " + fp )
                    files.append( fp )
            logging.debug('config files: ' + str(files))
        except:
            pass
        return files

    def context_for_filepath( self, filepath ):
        """
        python doesn't really like '/' in file names, so we do something stupid to avoid it
        """
        filepath = 'file:\\\\' + filepath
        filepath = filepath.replace( '/', '\\' )
        logging.debug("filepath " + str(filepath))
        return filepath
        
    def cat_file( self, filepath ):
        return [ i for i in self.prompt.tell( 'more ' + str(filepath), cursor=self.prompt.cursor('mode', 'enable'), output_wait=0.5 ) ]

    def get_running_config( self, context=None ):
        logging.debug('getting running config from context ' + str(context))
        if not context == None:
            if not self.prompt.change_to_context( context ):
                # if no contexts, that fine
                pass
        c = []
        for i in self.prompt.tell( 'show running-config', cursor=self.prompt.cursor('mode','enable'), output_wait=2, timeout=self.prompt.timeouts['long'] ):
            # logging.debug('> ' + str(i))
            if match( r'\r\s+\r', i ):
                i = i.replace( '\r\s+\r', '' )
            c.append(i.rstrip())
        if len(c):
            # remove until "ASA Version" from top
            for n,l in enumerate(c):
                if l.startswith('ASA '):
                   break 
            for i in xrange(0,n):
                c.pop(0)
            c.pop(-1)
            c.append('')
            # logging.debug("CONFIG: " + str(c))
            return c
        logging.warn("could not get running config for context " + str(context) )
        return None
    
    def get(self):
        """
        get all config files associated with the asa,
        we deal with xml files stored on flash,
        as well as the show running config for each context (if applicable)
        """

        self.prompt.terminal_buffer()
        dc = DeviceConfigurations()
        # save xml files too
        r = compile( '(([a-zA-z0-9]|_)+\.xml)' )
        for f in self.list_files( r ):
            logging.debug('getting config file ' + str(f))
            this = self.cat_file( f )
            c = self.context_for_filepath( f )    
            # logging.debug("context: " + str(c) + ", " + str(this))
            dc.set_config( this, self, context=c )
        contexts = self.prompt.list_contexts( fail_okay=True )
        logging.debug("CONTEXTS: %s" % (contexts,))
        # asa's could be configured without contexts
        if len( contexts ) == 0:
            this = self.get_running_config()
            if not this == None:
                dc.set_config( this, self )
        else:
            for c in contexts:
                this = self.get_running_config( context=c )
                if not this == None:
                    dc.set_config( this, self, context=c )
        return dc
    
    def commit(self):
        return self.prompt.ask( 'write memory', cursor=self.prompt.cursor('mode','enable'), timeout=self.prompt.timeouts['long'] )
        

class UsersCiscoAsa( Users ):
    matches = [
        r'^(?P<line>\d) .* (?P<user>(\w|\.|\-|\@)+)$',
    ]

    def get( self ):
        return self._yield_matches( 'sh ssh sessions', cursor=self.prompt.cursor('mode','enable'), regex_matches=self.matches )

class SystemCiscoAsa( System ):
    config = ConfigCiscoAsa
    model = ModelCiscoIos
    users = UsersCiscoAsa

    matches = [
        r'Hardware:   (?P<model>(\w|\-)+), ',
        
    ]

    def get(self):
        c = []
        members = []
        item = {}
        for l in self.prompt.tell( 'show version' ):
            m = []
            # logging.error( "> " + str(l) )
            if m.append( match( r'Hardware:   (?P<model>(\w|\-)+), ', l ) ) or m[-1]:
                item['model'] = m[-1].group('model')
            elif m.append( search( r'^Cisco Adaptive Security Appliance Software Version (?P<sw_version>.*)$', l ) ) or m[-1]:
                item['sw_version'] = m[-1].group('sw_version')
            elif m.append( search( r'^System image file is \"(?P<sw_image>.*)\"$', l ) ) or m[-1]:
                item['sw_image'] = m[-1].group('sw_image')
        if len( item.keys() ):
            item['number'] = 1
            members.append( item )
            logging.debug('model info: ' + str(members))
            return sorted( members, key=lambda k: k['number'] )
        raise DeviceException, 'could not determine information about system'
        

class RoutesCiscoAsa( RoutesCisco ):
    matches = {
        'o' : r'^O (?P<ospf_type>\w+)?\s+ (?P<prefix>\d+\.\d+\.\d+\.\d+) (?P<netmask>\d+\.\d+\.\d+\.\d+)',
        'o2': r'^O(\s+|\*)(?P<ospf_type>\w+)?\s+(?P<prefix>\d+\.\d+\.\d+\.\d+) ((?P<netmask>\d+\.\d+\.\d+\.\d+))? \[\d+/\d+\] via (?P<next_hop>\d+\.\d+\.\d+\.\d+), .*, (?P<interface>(\w|\-|\+)+)',
        'p': r'^\s+\[\d+/\d+\] via (?P<next_hop>\d+\.\d+\.\d+\.\d+), .*, (?P<interface>(\w|\-|\+)+)',
        'h' : r'^\s+(?P<prefix>\d+\.\d+\.\d+\.\d+)(/(?P<netmask>\d+\.\d+\.\d+\.\d+))',
        'c' : r'^C\s* (?P<prefix>\d+\.\d+\.\d+\.\d+) (?P<netmask>\d+\.\d+\.\d+\.\d+) is directly connected, (?P<interface>(\w|\-|\+)+)$',
    }
    command = 'show route'


class ArpsCiscoAsa( Arps ):
    matches = {
        'show arp': r'^\s+(?P<interface>(\w|\-|\+)+) (?P<ip_address>\d+\.\d+\.\d+\.\d+) (?P<mac_address>\w+\.\w+\.\w+)',
        'show ipv6 neighbor': r'(?P<ip_address>\S+)\s+(?P<age>\d+)\s+(?P<mac_address>\w+\.\w+\.\w+)\s+(?P<state>\w+)\s+(?P<interface>(\w|\-|\+)+)',
    }
    
    def _get(self):
        for m in self.matches.keys():
            for d in self.prompt.tell_and_match( m, self.matches[m] ):
                d['mac_address'] = d['mac_address'].lower()
                yield d['mac_address'] + '-' + d['ip_address'], d


class Layer3CiscoAsa( Layer3 ):
    routes = RoutesCiscoAsa
    arps = ArpsCiscoAsa

class CiscoAsa( Device ):
    prompt = PromptCiscoAsa
    system = SystemCiscoAsa
    
    layer3 = Layer3CiscoAsa

    def validate( self ):
        return self.prompt.ask( 'show version | inc Cisco Adaptive Security Appliance Software Version', cursor=[ self.prompt.cursor('mode','enable'), self.prompt.cursor('mode','exec') ] )

