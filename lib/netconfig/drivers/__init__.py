import logging
from re import compile, match, search, sub, DOTALL
from time import sleep
import traceback
from string import translate
from netconfig import util
from netconfig.Connector import *
from netconfig.backup.configuration import DeviceConfigurations

from lxml import etree

from slac_utils.net import prefixlen_to_netmask, truncate_physical_port, netmask_to_prefixlen, to_ip
from slac_utils.string import strip_ansi, strip_non_ascii

try:
    from collections import OrderedDict
except:
    from ordereddict import OrderedDict

#######################################################################
# Exceptions
#######################################################################

class DeviceException( Exception ):
    pass

class IncompatibleDeviceException( DeviceException ):
    pass

#######################################################################
# Generic Prompt
#######################################################################

class Prompt( object ):
    """
    a class to represent input and output to the command line of a device via a connector
    provides meaningful methods to interact, handling errors and different modes for the prompt
    """
    connector = None
    expect_mapping = {}
    expect_array = []
    
    # we keep some state so that we know what to look for
    # a prompt is the string that the terminal sees that awaits input from the user
    # preamble: is the constant in the prompt (typically a hosname)
    # context: is a context that defines what can be done
    # modes: is one of the groupings of prompt types listed below
    # type: is actual prompt (what pexepct searches for)
    # cursor: is an class internal represenation of the current context, mode and type.
    #   this is of the format <mode>::<type>@<context>
    
    preamble = None

    current_cursor = None
    current_context = None

    # use this to help determine the context the prompt is currently in
    context_regex = None
    
    # rpc
    rpc_cmd_append = ' | xml'
    
    mode = {
        'exec':     "\>",
        'enable':   "\#",
        'config-line': '\(config-line\)\#',
    }
    
    error = {
        'input': "Invalid input detected at",
        'incomplete': "Incomplete command."
    }
    
    interact = {
        'enable_password': 'Password: ',
        'pager'     : '\s?--More--\s?.*$',  # pager (press space for more)
        'question'  : "\[.*\](\:|\?) $",
    }
    
    expectations = {} # all of the above modes
    expect_array = []  # prompts to expect from the terminal
    expect_mapping = [] # what the expects cursors map to, same index as expect_array
    
    interaction_keys = {
        'carriage_return': "\x0d",
        'pager': "\x20",
    }
    
    timeouts = {
        'login': 5,
        'short': 8,
        'medium': 15,
        'long': 60,
        'very_long': 900,
    }
    
    stanza_prefix = r'^\s+'
    
    # when trying to determine the prompt, we may be stuck in the wizard, use the following responses
    wizard_responses = {}
    
    # some devices don't buffer input too well, so increase this to wait in secs before parsing
    output_wait = 0.001
    # wait this long in seconds to flush the output from the previous cmd
    flush_wait = 0.01
    
    def __init__(self, connector):
        self.connector = connector
        self.expectations = {
            'mode': self.mode,
            'error': self.error,
            'interact': self.interact,
        }
        self.preamble = None
        self.current_cursor = None
        self.current_context = None
        # setup what we should be looking for in the prompt
        self.setup_prompts()
    
    def generate_prompt(self, preamble=None, mode=None, type=None, symbol=None, context=None, current=True ):
        s = symbol
        if mode == 'mode':
            if not preamble == None:
                s = preamble + symbol
        return s
    
    
    def stanza( self, cmd, **kwargs ):
        # logging.info("CMDL %s" % (cmd,))
        self._enter_prompt = self.current_cursor
        if self.ask( cmd, **kwargs ):
            return self
        return None
        
    def __enter__(self,*args,**kwargs):
        return self
        
    def __exit__(self,*args,**kwargs):
        # logging.error("ARGS: %s %s " % (args,kwargs))
        self.ask( '', cursor=self._enter_prompt )
        del self._enter_prompt
        
    
    def setup_prompts( self, expect=['interact', 'error', 'mode'], context=None, preamble=None, current=True ):
        if preamble == None:
            preamble = self.preamble
        # logging.debug("setting up prompts for %s, context %s..." % (preamble,context,))
        self.expect_array = []
        self.expect_mapping = []
        # faciliate mapping the prompts as seen through pexpect to some prompt we can use
        # we need to ensure that errors and unexpected stuff are first in list
        for k in expect:
            v = self.expectations[k]
            for x,y in v.iteritems():
                self.expect_mapping.append( { 'cursor': self.cursor( k, x, context=context ), 'type': k } )
                self.expect_array.append( 
                    self.generate_prompt( preamble=preamble, mode=k, type=x, symbol=y, context=context, current=current ) 
                )

        # logging.debug("  array: " + str(self.expect_array) )
        # logging.debug("  mapping: " + str(self.expect_mapping) )

    def discover_prompt( self, empty_prompt=False, escape_prompt=True, output_wait=0.005 ):
        """
        try to determine the current prompt by analysing what comes out
        """
        logging.debug("discovering prompt...")
        # generate empty list of mode prompts (no preamble)
        self.setup_prompts( expect=['mode'], preamble='' )
            
        # send empty line and use the index of the output to determine the type
        # clear crap
        # logging.debug(" clearing...")
        self.connector.session.before.split("\n").pop().strip()
        self.connector.session.sendline()

        last_prompt = ''
        this_prompt = 'unknown'
        # limit number of tries
        try_count = 1
        max_tries = 3
        while not last_prompt == this_prompt:
            # get the last line from the buffer
            before = self.connector.session.before
            # logging.debug(" BEFORE: " + str(before))
            last_prompt = before.split("\n").pop().strip()
            # logging.debug(" LAST: " + str(last_prompt))

            # try to exit any stupid wizard
            for i in self.wizard_responses:
                # logging.debug("  I: '" + str(i) + "', '" + str(last_prompt) + "'")
                if str(last_prompt).find( str(i) ) > 0:
                    logging.debug("  attempting to exit wizard, sending " + str(self.wizard_responses[i]) )
                    self.connector.send( self.wizard_responses[i] + "\n" )
                    last_prompt = ''
                    try_count = try_count - 1
                
            self.connector.session.sendline()
            if output_wait > 0:
                sleep( float(output_wait) )
            after = self.connector.session.before
            # logging.debug(" AFTER: " + str(after))
            this = after.split("\n").pop().strip()

            if not this == '':
                this_prompt = this
            # logging.debug( "    last: '%s', this: '%s', %s/%s" % (last_prompt, this_prompt, try_count, max_tries) )
            try_count = try_count + 1
            if try_count > max_tries:
                raise ConnectorException, 'could not auto determine the prompt'

        # if the prompt is discovered as being blank
        if not empty_prompt and this_prompt == '':
            raise ConnectorException, 'discovered empty prompt'

        # remove ansi stuff
        this_prompt = strip_ansi( this_prompt )
        # escape prompt?
        if escape_prompt:
            this_prompt = this_prompt.replace( '[', '\[' ).replace( '(', '\(' )
            this_prompt = this_prompt.replace( ']', '\]' ).replace( ')', '\)' )
        logging.debug(" almost done... %s" % this_prompt)

        # analyse the prompt for the preamble/context
        if not self.context_regex == None:
            logging.debug('  looking for contextual prompt, using %s...' %(self.context_regex,) )
            # reset the prefix on the prompt
            m = []
            if m.append( match( self.context_regex, str(this_prompt) ) ) or m[-1]:
                self.preamble = m[-1].group('preamble')
                try:
                    self.current_context = m[-1].group( 'context' )
                except:
                    self.current_context = None
                logging.debug( "    found context=%s, preamble=%s" % (self.current_context,self.preamble) )
            else:
                logging.debug("  could not determine context")
        else:
            self.preamble = str(this_prompt)

        # send some commands to ensure that this device is the correct one 
        #logging.debug("current context: %s" % (self.current_context,))
        self.setup_prompts( context=self.current_context )
        # check to make sure it's correct
        try:
            if not self.ask( '', output_wait=0.1 ):
                raise Exception, 'bad!'
            return True
        except:
            raise ConnectorException, 'prompt incompatible'

    def cursor( self, mode, type=None, context=None ):
        """
        representation of an expected prompt that is understood by Prompt() only
        """
        if mode in self.expectations:
            if not type == None and type in self.expectations[mode]:
                return str(mode) + '::' + str(type) + '@' + str(context)
            # return array if no type
            else:
                p = []
                for t in self.expectations[mode]:
                    p.append( str(mode) + '::' + str(t) + '@' + str(context))
                return p
        else:
            s = 'unknown prompt type ' + str(mode) + ' for ' + str(type) + " with context=" + str(context)
            logging.error(s)
            raise DeviceException, s
    
    def inverse_cursor( self, cursor ):
        """
        from a given cursor, determine, the mode, type and context
        """
        prompt, context = cursor.split('@')
        if context == 'None':
            context = None
        mode, type =  prompt.split('::')
        return mode, type, context
    
    # def prefix( self, string ):
    #     """ set a better indication of the real mode to search for """
    #     for n in xrange( 0, len(self.expect_array) ):
    #         if self.expect_mapping[n]['type'] == 'mode':
    #             self.expect_array[n] = string + self.expect_array[n]

    def mode_interactive( self, escape_character='\x1d' ):
        """ enter interactive mode for the prompt (ie allow user input) """
        char_map ={
            '\x1d': '^]'
        }
        print( "Entered interactive mode, use " + char_map[escape_character] + " to exit.")
        # get mode ready for user
        self.connector.sendline( '' )
        return self.connector.interact( escape_character=escape_character )
    
    def terminal_buffer( self, length=0 ):
        """
        set the terminal to output 'length' lines before requiring user input for next page 
        """
        pass

    def mode_exec(self):
        raise NotImplementedError, 'mode_exec not implemented'
    
    def mode_enable(self):
        raise NotImplementedError, 'mode_enable not implemented'

    def mode_config(self):
        raise NotImplementedError, 'mode_config not implemented'

    def list_contexts( self ):
        """
        return a list of the available contexts on this device
        """
        raise NotImplementedError, 'dunno how to list contexts'

    def change_to( self, cursor ):
        """
        switch to the cursor requested
        """
        mode, type, context = self.inverse_cursor( cursor )
        logging.debug( ' change to mode=%s, type=%s, context=%s: cursor=%s' % (mode,type,context,cursor) )
        # change to the context if not same
        ok = False        
        if mode == 'mode':
            mode_mapping = {
                'exec': self.mode_exec,
                'enable': self.mode_enable,
                'config': self.mode_config,
                # 'config-sync': self.mode_config_sync,
            }
            # if not type in mode_mapping:
            #     raise NotImplementedError, 'do not know how to change to mode ' + str(type)
            if type in mode_mapping:
                logging.debug("  change to type %s, context %s " %(type,context))
                ok = mode_mapping[type]()

        if ok and not context == None and not self.current_context == context:
            # get new expects for this context
            logging.debug('changing context to %s' % context)
            if self.change_to_context( context ):
                ok = self.discover_prompt()
            
        return ok

    def change_to_context( self, context ):
        """
        switch to the specified context
        """
        pass

    def expect( self, timeout=0 ):
        # logging.debug("    expecting: %s" % (self.expect_array))
        i = self.connector.expect( self.expect_array, timeout=timeout )
        # logging.debug("     got %s: index %s %s" % (self.expect_array[i],i,self.expect_mapping[i]))
        self.current_cursor = self.expect_mapping[i]['cursor']
        # logging.debug("     found cursor %s"% self.current_cursor)
        return self.current_cursor

    def wait_for_output( self, timeout=timeouts['short'] ):
        """ wait until timeout for something in the output from the connector that we know of """
        if timeout == None:
            timeout = self.timeouts['short']
        pager_prompt = self.cursor( 'interact', 'pager' )
        p = pager_prompt
        output = []
        while p == pager_prompt:
            p = self.expect( timeout=float(timeout) )
            # logging.debug(" > p %s %s" % (p,pager_prompt) )
            for i in self.connector.get_buffer():
                # logging.debug("   b> %s %s" % (p,i,))
                output.append( strip_non_ascii( strip_ansi(i.rstrip()) ) )
            if p == pager_prompt:
                logging.debug("    sending pager %s" % (self.interaction_keys))
                self.connector.send( self.interaction_keys['pager'] )
        return p, output


    def process_output( self, timeout=None, error_okay=False ):
        last_output = None
        first = True
        c, output = self.wait_for_output( timeout=timeout )
        mode, t, context = self.inverse_cursor( c )
        # logging.debug("   > m=%s, t=%s, m c=%s: %s" % (mode,t,context,output))
        if mode == 'error':
            logging.debug("  command error'd %s" % (c,))
            if not error_okay:
                raise DeviceException, "error executing command (mode %s type %s)" % (mode, t)
        for i in output:
            # remove the first and last lines
            if last_output:
                # logging.debug("    mid> %s" % last_output)
                yield last_output
            if not first:
                last_output = i
            first = False
        # logging.debug("    end> %s" % last_output)
        yield last_output
        return

    def new_line( self, timeout=timeouts['short'], output_wait=0 ):
        # start fresh and determine the current prompt
        self.connector.sendline( '', carriage_return=self.interaction_keys['carriage_return'] )
        return [ i for i in self.process_output( timeout ) ]

    def send_command( self, cmd, output_wait=0 ):
        self.connector.sendline( cmd, carriage_return=self.interaction_keys['carriage_return'] )
        if output_wait > 0:
            # logging.debug("  output wait pause for " + str(output_wait))
            sleep(output_wait)

    def tell( self, cmd, timeout=timeouts['short'], cursor=None, preempt=True, output_wait=None, flush_wait=None, suppress_command_output=False, post_prempt=True, error_okay=False, **kwargs ):
        """
        generator method to provide the output from the cmd send to the device 
        if the cursor if defined, it will enter into the relevant mode, type, and context before executing the cmd
        preempt will not try to send cr before in order to clear the buffers
        """
        if output_wait == None:
            output_wait = self.output_wait
        if flush_wait == None:
            flush_wait = self.flush_wait

        # TODO: should probably check the command for overflows
        command = cmd
        if suppress_command_output:
            command = '********'
        logging.debug('tell "%s" in wanted_cursor=%s, preempt=%s, timeout=%s, flush=%s' % (command,cursor,preempt,timeout,flush_wait))

        # clean the bufer first to ensure there's no junk in our output
        cleaning = True
        while cleaning:
            # logging.debug("  cleaning...")
            try:
                crap = self.connector.session.read_nonblocking( size=64, timeout=flush_wait )
                logging.debug("  cleaned buffer: %s" %(crap))
            except:
                # logging.debug('  flush failed')
                cleaning = False

        if preempt:
            logging.debug('  sending initial CR')
            for i in self.new_line( timeout=timeout ):
                pass
                # logging.debug("   I: %s" % i)
        
        wanted_cursor = []
        if not cursor == None:
            # see what modes we are okay with running this cmd under
            if not type( cursor ) == list:
                wanted_cursor.append( cursor )
            else:
                for m in cursor:
                    wanted_cursor.append( m )
            # logging.debug("  cursor current=%s, wanted=%s" % (self.current_cursor,wanted_cursor) )
            if not self.current_cursor in wanted_cursor:
                ok = False
                for c in wanted_cursor:
                    if self.change_to( c ):
                        ok = True
                        break
                if not ok:
                # if not self.change_to( wanted_cursor[0] ):
                    raise DeviceException, 'dunno how to change into prompt ' + str(wanted_cursor) + ' from prompt ' + str(self.current_cursor)

        if preempt:
            # clean
            logging.debug("  sending final CR")
            self.new_line( timeout=timeout )
            # check to ensure it's correct prompt
            # logging.debug("  preempt cursor %s" % (self.current_cursor,))
            if len(wanted_cursor) and not self.current_cursor in wanted_cursor:
                raise DeviceException, 'could not get into cursor(s) %s from cursor %s' % (wanted_cursor,self.current_cursor)

        # finally send the cmd and generate output
        logging.debug('  sending command: "%s", output_wait=%s, timeout=%s' % (command,output_wait,timeout) )
        if cmd == None:
            logging.error("NO COMMAND? %s" % (cmd,))
        self.send_command( cmd.rstrip(), output_wait=output_wait )
        # some strange bug, where waiting will result in no data, but after will 
        logging.debug("  initial check")
        for i in self.process_output( timeout=timeout, error_okay=error_okay ):
            yield i
        
        # send an ending carriage return
        # if preempt and lines == 0:
        if preempt and post_prempt:
            logging.debug('  sending post CR')
            # logging.debug("    hit output bug")
            for i in self.new_line( timeout=timeout ):
                yield i
        return
        
    def respond( self, interact={}, timeout=timeouts['short'] ):
        # deal with interactive response requirements; using interact from parameters
        mode,cursor,context = self.inverse_cursor( self.current_cursor )
        logging.debug("   found interactive response required %s (%s / %s)" % (self.current_cursor,cursor, interact))
        if mode == 'interact':
            res = False
            if cursor in interact:
                logging.debug("  answering '%s'" % (interact[cursor],))
                self.connector.sendline( interact[cursor], carriage_return=self.interaction_keys['carriage_return'] )
                # self.expect( self.timeouts['short'] )
                for i in self.process_output( timeout=timeout ):
                    yield i
            elif cursor == 'username':
                res = self.ask( self.connector.user, preempt=False )
            elif cursor == 'enable_password':
                p = self.connector.enable_password
                if p == None:
                    raise Exception, 'no enable password defined'
                res = self.ask( p, preempt=False, suppress_command_output=True )
            else:
                raise Exception, 'do not know how to deal with interact prompt %s' % cursor 

        return
        
    def request( self, cmd, timeout=timeouts['short'], cursor=None, preempt=True, output_wait=None, suppress_command_output=False, fail_okay=False, error_on_null_output=False, interact={} ):
        ok = True
        out = []
        # determine interactive input
        interactive = [ p for p in self.cursor('interact') ]
        # go!
        try:
            for r in self.tell( cmd, timeout=timeout, cursor=cursor, preempt=preempt, output_wait=output_wait, suppress_command_output=suppress_command_output, post_prempt=False ):
                logging.debug("  request> %s" % r)
                out.append( r )
                while self.current_cursor in interactive:
                    logging.debug(" +++ current cursor: %s -> %s" % (self.current_cursor,interact) )
                    for s in self.respond( interact, timeout=timeout ):
                        # logging.debug("   > %s" % (s,))
                        if s:
                            out.append(s)
            self.new_line()
        except Exception, e:
            logging.debug("error: %s" % (e,))
            ok = True if fail_okay else False
        if error_on_null_output and c == 0:
            ok = False
        logging.debug("finished request: %s" % ok)
        if not ok:
            raise Exception, 'request failed'
        return out

    def ask( self, *args, **kwargs ):
        """
        true/false response from prompt, errors are handled
        """
        try:
            logging.debug("asking...")
            out = self.request( *args, **kwargs )
            logging.debug("  true: %s" % (out,))
            return True
        except Exception, e:
            logging.debug("  false")
            if 'fail_okay' in kwargs and bool(kwargs['fail_okay']):
                return False
            else:
                raise e

    def parse_block( self, block, regexes=[] ):
        data = {}
        # logging.debug("      parsing block")
        for b in block:
            # logging.debug("       > %s" % (b,))
            for r in regexes:
                # logging.debug("        trying r=%s" % (r,))
                m = search( r, b )
                if m:
                    # logging.debug("         match!")
                    for k,v in m.groupdict().iteritems():
                        # logging.debug("        >: %s = %s" % (k,v))
                        data[k] = v
                    break
        # logging.debug("      >: data: %s" % (data,))
        return data

    def get_blocks( self, cmd, stanza_prefix, ignore_blanks=False, **kwargs ):
        block = []
        for o in self.tell( cmd, **kwargs ):
            # logging.debug("  > '%s'" % (o,))
            if ( ignore_blanks and o == '' ) or match( stanza_prefix, o ):
                # logging.debug('    adding %s to %s' % (o,block))
                block.append( o )
            else:
                if len(block):
                    # logging.debug('    block: %s' % (block,))
                    yield block
                block = [ o ]
        return

    def tell_and_match( self, cmd, regex, **kwargs ):
        """
        basically does a tell with a groupdict() return from the regex for each line outputted
        """
        if not 'cursor' in kwargs:
            kwargs['cursor'] = self.cursor('mode','enable')
        regexes = regex
        if not type(regex) == list:
            regexes = [ regex ]
        for o in self.tell( cmd, **kwargs ):
            # logging.debug('  > ' + str(o))
            for r in regexes:
                m =  match( r, o )
                if m:
                    d = m.groupdict()
                    logging.debug('    >: found %s' % (d,))
                    yield d
                    break
        return

    def tell_and_match_block( self, cmd, regexes, **kwargs ):
        """
        like a tell_and_match, but does numerous matches on each stanza
        """
        for b in self.tell_and_get_block( cmd, **kwargs ):
            yield self.parse_block( b, regexes )
        return

    def tell_and_get_block( self, cmd, **kwargs ):
        stanza_prefix = self.stanza_prefix
        if stanza_prefix in kwargs:
            stanza_prefix = kwargs['stanza_prefix']
        for b in self.get_blocks( cmd, stanza_prefix, **kwargs ):
            # logging.debug("B= %s" % (b,))
            yield b
        return
        
    def tell_and_match_by_index( self, cmd, index, regex, begin=None, end=None, **kwargs ):
        """
        will match all items in regexes for all command output, and merges each line to common index that must exist in each matched line
        """
        regexes = regex
        if not type(regex) == list:
            regexes = [ regex ]
        found = {}
        wanted = True if begin == None else False
        
        for o in self.tell( cmd, **kwargs ):

            # logging.error("wanted: %s, beg %s, end: %s " % (wanted, begin, end))
            if wanted == False and begin:
                if match( begin, o ):
                    wanted = True
            if not wanted:
                continue
                
            if end:
                if match( end, o ):
                    # logging.error("ending")
                    break

            # logging.debug('  > ' + str(o))
            for r in regexes:
                m =  match( r, o )
                if m:
                    d = m.groupdict()
                    if not d[index] in found:
                        found[d[index]] = {}
                    for k in d:
                        found[d[index]][k] = d[k]
        for d in found:
            yield found[d]
        return
        
    def rpc( self, cmd, timeout=timeouts['short'], cursor=None, preempt=False, output_wait=None, flush_wait=None, suppress_command_output=False ):
        """ netconf rpc """
        # TODO: strip namespaces?
        out = '\n'.join(self.tell( cmd + self.rpc_cmd_append ))
        # logging.error("OUT: %s" % (out,))
        return etree.fromstring( out )

#######################################################################
# Generic Components
#######################################################################


class Component( object ):
    """
    a generic object that allows query and setting of device parameters
    use a hierachy of parent and child components to help segment logical or physical components
    """
    
    prompt = None # how to communicate with the device
    
    parent = None
    children = []

    _cache = None
    
    def __init__(self, prompt, parent=None, **kwargs ):
        # just ensure that we have a way to communicate to the device, also provide the parent so that the child may call things directly
        self.prompt = prompt
        self.parent = parent
        # register the children components
        for i in self.children:
            this = getattr(self, i)
            if not this == None:
                # logging.debug("  initiating component " +str(this) )
                setattr( self, str(i), this( self.prompt, parent=self ) )
            
    def initiate(self):
        pass
    
    def __getattribute__( self, name ):
        """
        catch all method to indicate that it's not implemented
        """
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            raise NotImplementedError, "method '" + str(name) + "' has not been implemented for this component " + str(type(self))

    def get( self, cache=False, **kwargs ):
        pass

    def __iter__(self):
        if self._cache == None or len(self._cache.keys()) == 0:
            if self._cache == None:
                self._cache = {}
            for k, d in self._get():
                self._cache[k] = d
        if self._cache:
            for k,v in self._cache.iteritems():
                yield k,v
        return
        
    def _on(self, var):
        for k,d in self:
            if var in d:
                yield k, d[var]
        return


class ComponentList( list ):
    """
    Representation of a listable, searchable series of components
    """
    prompt = None
    parent = None
    children = []

    _cache = None

    def __init__( self, prompt, parent=None ):
        self.prompt = prompt
        self.parent = parent
        
    def initiate(self):
        pass

    def _get(self):
        raise NotImplementedError, '_get()'

    def __iter__(self):
        if self._cache == None or len(self._cache.keys()) == 0:
            if self._cache == None:
                self._cache = {}
            for k, d in self._get():
                self._cache[k] = d
        if self._cache:
            for k,v in self._cache.iteritems():
                yield k,v
        return
        
    def _on(self, var):
        for k,d in self:
            # logging.debug(" k: %s,\tvar: %s,\td: %s" % (k,var,d))
            if var in d:
                yield k, d[var]
        return

    def __getattribute__( self, name ):
        """
        catch all method to indicate that it's not implemented
        """
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            raise NotImplementedError, "method '" + str(name) + "' has not been implemented for this device"

    def get( self, item=None ):
        """
        get the port object for the port index
        """
        if item == None:
            return [ d for k,d in self ]
        return [ d for k,d in self if k == d ]

    def filter( self, string=None, **kwargs ):
        for k,p in self._get( port=string ):
            f = self._filter( p, **kwargs )
            if f:
                yield f
        return
        
    def _filter( self, port, **kwargs ):
        """
        to be run after a self.filter() to reduce the list of matching ports
        """
        good = True
        for k,v in kwargs.iteritems():
            if k in port:
                # logging.debug("filtering %s %s (key %s, value %s)" % (k,v,k in port, port[k]))
                if not v == port[k]:
                    good = False
                    break
        if good:
            return port
        return None

#######################################################################
# Implementation Components
#######################################################################

class Ports( ComponentList ):
    """
    Object representation of the ports available on the device
    """

    conf_sync = None

    def enter_port_mode( self, port ):
        """
        change into the port configuration prompt
        """
        raise NotImplementedError, 'enter port mode not implemented'
    
    def exit_port_mode( self, port ):
        pass
        
    def stanza( self, port_obj, **kwargs ):
        raise NotImplementedError, 'stanza'

    def __enter__( self, *args, **kwargs ):
        return self.prompt
        
    def __exit__(self, *args, **kwargs):
        self.ask( '', cursor=self._enter_prompt )
        del self._enter_prompt

        
    def set_type( self, port, value, other, enter_port_mode=True ):
        type_map = {
            'access': self.set_type_access,
            'trunk': self.set_type_trunk,
            'private-vlan host': self.set_type_privatevlan_host
        }
        logging.debug("setting port type %s" %(value,) )
        ok = False
        if value in type_map:
            # clear the settings first
            self.set_type_clear( port, value, other, enter_port_mode=enter_port_mode )
            if 'vlan' in other:
                ok = type_map[value]( port, other['vlan'], other, enter_port_mode=enter_port_mode )
            self.set_type_clear_post( port, value, other, enter_port_mode=enter_port_mode )
        # HMMM
        return ok

    def set( self, port=None, port_object={}, initial_check=True ):
        """
        given the Port object, change the port settings to match
        some intelligence is used to determine only things that need to be changed
        if successful, return True
        if some differences exist between before and after the request, return False
        if nothing neede to be done, return None
        """
        # need to do by specific order due to duplex/speed etc
        set_map = OrderedDict([
            ( 'type',  self.set_type ),
            ( 'vlan', self.set_type_access ),
            ( 'trunk', self.set_type_trunk ),
            ( 'bpduguard',    self.set_bpduguard ),
            ( 'portfast',    self.set_portfast ),
            ( 'alias', self.set_alias ),
            ( 'speed', self.set_speed ),
            ( 'duplex', self.set_duplex ),
            ( 'autoneg', self.set_autoneg ),
            ( 'state', self.set_state ),
            ( 'voice_vlan', self.set_voice_vlan ),
            ( 'native_vlan', self.set_native_vlan ),
            ( 'logging', self.set_logging ),
            ( 'security', self.set_security ),
            ( 'storm-control', self.set_storm_control ),
            ( 'portnoneg', self.set_portnoneg ),
            ( 'cdp', self.set_cdp ),
            ( 'lldp', self.set_lldp ),
            ( 'dhcp_snooping', self.set_dhcp_snooping ),
        ])
        none_okay_fields = ( 'alias', )
        # okay jus tto have true value
        true_okay_fields = ( 'voice_vlan', )

        # try some smarts on what port actually is
        p = {}
        if type(port) == str:
            p['port'] = port
        elif type(port) == Port:
            p = port

        if not 'port' in port_object:
            port_object['port'] = port

        if port == None:
            p = port_object
            
        port_object = Port( port_object )
        logging.debug('setting port with ' + repr(port_object) )

        # determine what actually nees to be done
        diff = {}
        # first lets' get the most current details of the port
        if initial_check:
            current = self.get( p['port'] )
            logging.debug("  current port: " + str(current))

            # now determine the diff from what we ask for
            for i in current:
                logging.debug("   diffing %s" % (i,))
                if i in ( 'port', ):
                    continue
                if i in port_object and not current[i] == port_object[i]:
                    # TODO: ignore None? will anything be bad? like alias?
                    if not port_object[i] == None or i in none_okay_fields:
                        diff[i] = port_object[i]
                        logging.debug('    %s -> %s' % (current[i],port_object[i]))
            logging.debug("  diff port: " + str(diff) )
        
            if len( diff.keys() ) == 0:
                # logging.debug('  no changes required')
                return None, {}
        else:
            diff = port_object

        # do something
        
        if self.enter_port_mode( p['port'] ):
            logging.debug('making changes to port %s: %s' % (p,diff))
            done = {}
            for k in set_map.keys():
                # make sure we're in the interface config mode
                # logging.debug("current cursor: %s" % (self.prompt.current_cursor) )
                if not self.prompt.current_cursor == self.prompt.cursor('mode','config-if'):
                    if not self.enter_port_mode( p['port'] ):
                        raise DeviceException, 'could not re-enter port mode'
                
                if not k in diff: # or diff[k] == None:
                    logging.debug("   skipping %s" % (k,))
                    continue

                logging.debug("   changing %s -> %s" %(k,diff[k]) )
                if set_map[k]( p['port'], diff[k], p, enter_port_mode=False ):
                    done[k] = diff[k]
                else:
                    logging.warn("  failed %s! %s" % (p['port'],k,))

            # do post 
            self.exit_port_mode( port )                
            
            # scan port again to ensure match with request
            logging.debug("validating changes on port %s" %(p['port'],))
            after = self.get( p['port'] )
            # logging.debug("requested: " + str(port_object) + ", after port: " + str(after))
            failed = {}
            for i in after:
                if i in ( 'speed', 'duplex', 'port' ):
                    continue
                # logging.debug("    " + str(i) )
                if i in port_object:
                    if i == 'alias' and i in after and after[i] == None and port_object[i] == '':
                        # fine
                        pass
                    # ignore case
                    else:
                        a = after[i]
                        b = port_object[i]
                        try:
                            a = [ str(x).upper() for x in after[i] ]
                            b = [ str(x).upper() for x in port_object[i] ]
                        except:
                            pass
                        if not i in true_okay_fields and not a == b:
                            logging.warn('      request for %s failed: %s -> %s' % (i,port_object[i],after[i]) )
                            failed[i] = port_object[i]
                            
            if len( failed.keys() ) > 0:
                # logging.error("failed to change on " + str(p) + ": " + str(failed))
                return False, failed
            
            return True, after
            
        raise Exception, 'could not enter port mode'

    def filter( self, string=None, **kwargs ):
        raise NotImplementedError, 'filter() is not implemented'

    def on_port( self ):
        return self._on('port')
    def on_alias( self ):
        return self._on('alias')
    def on_admin_status( self ):
        return self._on('state')
    def on_op_status( self ):
        return self._on('protocol')
    def on_type( self ):
        return self._on('type')
    def on_duplex( self ):
        return self._on('duplex')
    def on_duplex_admin( self ):
        for k,v in self:
            if v['autoneg']:
                yield k, 'auto'
            else:
                yield k, v['duplex']
    def on_speed( self ):
        return self._on('speed')
    def on_speed_admin( self ):
        for k,v in self:
            if v['autoneg']:
                yield k, 'auto'
            else:
                yield k, v['speed']
    def on_portfast( self ):
        return self._on('portfast')
    def on_native_vlan( self ):
        for k,v in self:
            if 'native_vlan' in v:
                yield k, v['native_vlan']
            elif v['type'] in ( 'access', 'fex-fabric' ) and len( v['vlan'] ) == 1:
                yield k, v['vlan'][0]
            else:
                pass
    def on_vlans( self ):
        for k,v in self:
            if v['type'] == 'access' and len( v['vlan'] ) == 1:
                pass
            else:
                yield k, v['vlan']


class PortChannels( ComponentList ):

    def _get( self, *args, **kwargs ):
        raise NotImplementedError, 'port channels'

    def attach( self, port_channel, physical_port ):
        raise NotImplementedError, 'attach'
        
    def detach( self, port_channel, physical_por ):
        raise NotImplementedError, 'detach'
        
    def create( self, port_channel, vlan ):
        raise NotImplementedError, 'create'
        

class Port( dict ):
    """
    A single port
    """

    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def __enter__(self):
        """ don't forget to commit after """
        return self

    def __exit__(self):
        return self
        
    def commit(self):
        """ commit changes """
        raise NotImplementedError, 'with statement not yet supported'

    def update(self, *args, **kwargs):
        if args:
            if len(args) > 1:
                raise TypeError("update expected at most 1 arguments, got %d" % len(args))
            other = dict(args[0])
            for key in other:
                self[key] = other[key]
        for key in kwargs:
            self[key] = kwargs[key]

    def setdefault(self, key, value=None):
        if key not in self:
            self[key] = value
        return self[key]

    def __str__(self):
        t = []
        for i in ( 'alias', 'state', 'status', 'protocol', 'type', 'vlan', 'vlan_name', 'autoneg', 'speed', 'duplex', 'voice' ):
            if i in self:
                j = self[i]
                if isinstance(j,str):
                    j = "'%s'" % j
                t.append( "%s=%s" % (i,j) )
        return '<Port %s: %s>' % (self['port'], " ".join(t))

    def __setitem__( self, k, v ):
        # logging.debug( 'setting ' + str(k) + ' to ' + str(v))
        # if k == None or v == None:
        if k == None:
            return
        elif k == 'vlan' or k == 'vlan_name':
            # logging.debug("     %s type: %s: %s" %(k,type(v),v) )
            name = False
            if k == 'vlan_name': name = True
            a = []
            if not type(v) == list:
                v = str(v)
                for i in v.split(','):
                    if not name: i = int(i)
                    a.append( i )
            else:
                for i in v:
                    if not name: i = int(i)
                    a.append( i )
            logging.debug( '      %s=%s' % (k,a))
            v = a
        # store
        super( Port, self ).__setitem__( k, v )


class Config(Component):
    """
    representation of the configuration file/objects of the device
    """
            
    def get_running_config( self ):
        """ returns array of text lines for current config """
        raise NotImplementedError, 'get_running_config()'
            
    def get(self):
        """ returns a DeviceConfigurations object """
        self.prompt.terminal_buffer()
        c = None
        try:
            c = self.get_running_config()
        except:
            raise DeviceException, 'could not get current configuration'
        dc = DeviceConfigurations()
        dc.set_config( c, self )
        return dc

    def commmit(self):
        """ write the running config to flash """
        raise NotImplementedError, 'commit()'
        
class MultipleFileConfig( Config ):
    pass


class Model( Component ):
    """
    representation of the model information on a device
    """
    
    def get( self ):
        """ return a list of the model numbers on teh system, indexed by stack number """
        raise NotImplementedError, 'cannot determine models'


class Firmware( Component ):
    """
    deal with firmware updates
    """
    
    def image( self ):
        """ return a list of the images on teh system, indexed by stack number """
        raise NotImplementedError, 'cannot determine images'
        
    def version(self):
        """ return a list of the firmware versions on teh system, indexed by stack number """
        raise NotImplementedError, 'cannot determine firmware'
    
    def check_boot_variable( self, set_to=None ):
        pass
        
    def transfer_firmware_image( self, *paths ):
        raise NotImplementedError, 'transfer_firmware_image() not implemented'

    def firmware_image_to_version( self, image_path ):
        pass


class Password( Component ):
    
    def vty_login( self, password, clear_existing=True ):
        pass
        
    def login( self, user, password, clear_existing=True ):
        pass
    
    def enable( self, password, level=15, clear_existing=True ):
        pass
        
    def snmp_ro( self, community, access_list=None, clear_existing=True ):
        pass
        
    def snmp_rw( self, community, access_list=None, clear_existing=True ):
        pass
    

class Transceiver( ComponentList ):
    """
    Representation of Transceiver fru's
    """
    def on_type(self):
        return self._on('type')
    def on_rx(self):
        return self._on('rx')
    def on_tx(self):
        return self._on('tx')
    def on_temperature(self):
        return self._on('temperature')



class Module( ComponentList ):
    """
    representation of modules
    """
    def on_relative_position(self):
        return self._on('slot')
    def on_status(self):
            return self._on('status')

    
class FRU( Component ):
    """
    representation of field replacable units on device
    """
    transceiver = Transceiver
    module = Module
    # linecards, powersupply, fans
    children = [ 'transceiver', 'module' ]
    

class Users( Component ):
    """
    api to determine who's logged in
    """
    def get( self ):
        return []
    
class System( Component ):
    
    config = Component
    model = Component
    fru = Component
    firmware = Component
    password = Component
    users = Component
    
    children = [ 'config', 'firmware', 'model', 'fru', 'password', 'users' ]
    
    def reload(self, at=None, force=False, commit=False ):
        """
        reload the switch at the specified time, if not defined, do it now
        """
        pass

class Rfc2863( ComponentList ):

    def on_admin_status( self ):
        return self._on('admin_status')
    def on_connector_status( self ):
        return self._on('connector_status')
    def on_oper_status( self ):
        return self._on('oper_status')
    def on_alias( self ):
        return self._on('alias')

    def on_mtu( self ):
        return self._on('mtu')
    def on_speed( self ):
        return self._on('speed')

    def on_in_queue_drops( self ):
        return self._on('in_queue_drops')
    def on_in_queue_flushes( self ):
        return self._on('in_queue_flushes')
    def on_in_queue_size( self ):
        return self._on('in_queue_size')
    def on_in_queue_max( self ):
        return self._on('in_queue_max')

    def on_total_output_drops( self ):
        return self._on('total_output_drops')
    def on_queueing_strategy( self ):
        return self._on('queueing_strategy')

    def on_output_queue_size( self ):
        return self._on('output_queue_size')
    def on_output_queue_max( self ):
        return self._on('output_queue_max')
    def on_l2_ucast_bytes( self ):
        
        return self._on('l2_ucast_bytes')
    def on_l2_mcast_pkt( self ):
        return self._on('l2_mcast_pkt')
    def on_l2_ucast_pkt( self ):
        return self._on('l2_ucast_pkt')
    def on_l2_mcast_bytes( self ):
        return self._on('l2_mcast_bytes')
    def on_l3_in_ucast_bytes( self ):
        return self._on('l3_in_ucast_bytes')
    def on_l3_in_mcast_bytes( self ):
        return self._on('l3_in_mcast_bytes')
    def on_l3_in_ucast_pkt( self ):
        return self._on('l3_in_ucast_pkt')
    def on_l3_in_mcast_pkt( self ):
        return self._on('l3_in_mcast_pkt')

    def on_l3_out_ucast_bytes( self ):
        return self._on('l3_out_ucast_bytes')
    def on_l3_out_ucast_pkt( self ):
        return self._on('l3_out_ucast_pkt')
    def on_l3_out_mcast_bytes( self ):
        return self._on('l3_out_mcast_bytes')
    def on_l3_out_mcast_pkt( self ):
        return self._on('l3_out_mcast_pkt')

    def on_input_bytes( self ):
        return self._on('input_bytes')
    def on_input_no_buffer( self ):
        return self._on('input_no_buffer')
    def on_input_pkts( self ):
        return self._on('input_pkts')
    def on_input_ip_mcast( self ):
        return self._on('input_ip_mcast')
    def on_input_bcasts( self ):
        return self._on('input_bcasts')
    def on_input_giants( self ):
        return self._on('input_giants')
    def on_input_runts( self ):
        return self._on('input_runts')
    def on_input_throttles( self ):
        return self._on('input_throttles')
    def on_input_overrun( self ):
        return self._on('input_overrun')
    def on_input_errors( self ):
        return self._on('input_errors')
    def on_input_crc( self ):
        return self._on('input_crc')
    def on_input_frame_errors( self ):
        return self._on('input_frame_errors')
    def on_input_ignored( self ):
        return self._on('input_ignored')

    def on_output_bytes( self ):
        return self._on('output_bytes')
    def on_output_pkts( self ):
        return self._on('output_pkts')
    def on_output_bcasts( self ):
        return self._on('output_bcasts')
    def on_output_underruns( self ):
        return self._on('output_underruns')

    def on_interface_resets( self ):
        return self._on('interface_resets')

    def on_output_collisions( self ):
        return self._on('output_collisions')
    def on_output_errors( self ):
        return self._on('output_errors')
    def on_output_discards( self ):
        return self._on('output_discards')
    def on_output_buffer_failures( self ):
        return self._on('output_buffer_failures')
    def on_output_buffers_swapped_out( self ):
        return self._on('output_buffers_swapped_out')


class Stats( Component ):
    rfc2863 = Component
    children = [ 'rfc2863' ]
    

class Vlan( ComponentList ):

    def on_name( self ):
        return self._on('name')
    def on_status( self ):
        return self._on('status')
    def on_operational( self ):
        for k,v in self._on('status'):
            # logging.error( '%s %s' % (k,v) )
            if v == 'active':
                yield k, 'operational'
        return
    def add( self, number, name ):
        raise NotImplementedError, 'create'
    def remove( self, number ):
        raise NotImplementedError, 'delete'
    def __dict__(self):
        vlan_map = {}
        for k,v in self:
            vlan_map[k] = v
        return vlan_map
        
class SpanningTree( Component ):
    pass
    
class MacAddress( ComponentList ):

    def on_physical_port(self):
        return self._on('physical_port')

    def on_type(self):
        return self._on('type')
        
    def on_vlan(self):
        return self._on('vlan')

    def on_status(self):
        return self._on('status')

class Layer1( Component ):
    neighbour = Component
    children = [ 'neighbour' ]

class Layer2( Component ):
    vlan = Component
    spanningtree = Component
    mac_address = Component
    children = [ 'vlan', 'spanningtree', 'mac_address' ]


class Layer3( Component ):
    routes = Component
    arps = Component
    children = [ 'routes', 'arps' ]



class Routes( Component ):

    def on_local(self):
        return self._on('local')
        
    def on_netmask(self):
        return self._on('netmask')

    def on_prefix_len(self):
        return self._on('prefix_len')
        
    def on_next_hop(self):
        return self._on('next_hop')

    def on_prefix(self):
        return self._on('prefix')

class Arps( ComponentList ):
    
    def on_mac_address(self):
        return self._on('mac_address')
    def on_ip_address(self):
        return self._on('ip_address')
    def on_physical_port(self):
        return self._on('interface')
    def on_vlan(self):
        return self._on('vlan')


class Device( object ):
    """
    A generic device class
    """
    name = 'Generic'
    hostname = None
    
    prompt = Prompt
        
    system = System
    stats = Component
    ports = Ports
    portchannels = PortChannels
    layer1 = Layer1
    layer2 = Layer2
    layer3 = Layer3

    children = [ 'system', 'ports', 'portchannels', 'layer1', 'layer2', 'layer3', 'stats' ]

    def __init__( self, hostname=None, username=None, password=None, enable_password=None, connector_type='ssh', port=None, prime=None, **kwargs ):
        # create the connector
        self.connector = get_connector( connector_type, hostname, username, password, enable_password, port=port )
        self.hostname = hostname
        self.prime = prime
        # instantiate components
        self.prompt = self.prompt( self.connector ) # create from object
        for i in self.children:
            this = getattr(self, i)
            if not this == None:
                # logging.debug("initiating component " + str(this) )
                setattr( self, i, this( self.prompt, parent=self ) )

    def connect( self, timeout=None, options=None, empty_prompt=None, prime=None ):
        """ connect to the device, and keep tabs of the discovered prompt """
        # prime: if true, sends a carriage return on timeout (useful for serial connections)
        # set up variables
        if not timeout:
            if not self.prompt.connector.timeout == None:
                timeout = self.prompt.connector.timeout
            else:
                timeout = self.prompt.timeouts['login']
        if prime == None:
            prime = self.prime

        logging.debug( "connecting (timeout=%s)..." % (timeout))
        
        # determine what may be possible character strings to look for
        prompt_postambles = []
        for k,v in self.prompt.mode.iteritems():
            prompt_postambles.append( v )
        for k,v in self.prompt.interact.iteritems():
            prompt_postambles.append( v )
        logging.debug("  prompt postambles: " + str(prompt_postambles))
        # connect to the device and determine the prefix to the above character strings to get a better match on the real prompt
        if self.connector.connect( prompt_postambles=prompt_postambles, login_timeout=timeout, options=options, empty_prompt=empty_prompt, prime=prime, wizard_responses=self.prompt.wizard_responses ):
            # determine the current prompts and extra driver checks
            if self.prompt.discover_prompt( empty_prompt=empty_prompt ):
                logging.debug("matched prompt ok")
                try:
                    if not self.validate() == False:
                        logging.debug('validated driver ok')
                        return True
                except:
                    pass
                
        logging.debug('could not connect and validate')
        self.disconnect()
        raise IncompatibleDeviceException, 'device %s is not compatible with %s' % (self.hostname,self)

    def is_connected( self ):
        return self.connector.is_alive()

    def disconnect( self ):
        """ disconnect the connection """
        logging.debug("disconnecting")
        # logging.debug("%s" % (traceback.format_exc(),))
        return self.connector.disconnect()

    def priviledge_check(self):
        # ensure we have full access to the device
        return self.prompt.mode_enable()

    def validate( self ):
        """
        validate whether this device object is compatible
        typically run some commands and compare against known values
        """
        pass
    
    def tell( self, command, **kwargs ):
        return self.prompt.tell( command, **kwargs )
        
    def rpc( self, command, **kwargs ):
        return self.prompt.rpc( command, **kwargs )
    
    def get_component( self, component ):
        objects = component.split('.')
        logging.debug("initiating component %s" % (objects))
        obj = self
        for o in objects:
            obj = getattr( obj, o )
        logging.debug("  returning %s" % (type(obj)))
        return obj


#######################################################################
# Example usage
#######################################################################


def __main__( *args, **kwargs ):
    
    nc = NetworkDevice()
    for p in nc.ports:
        logging.error("Port " + str(p))
        
    for p in nc.ports.trunks:
        logging.error("Port " + str(p))
        
    for p in nc.ports.objects( type='private_vlan' ):
        logging.error("Port " + str(p))
