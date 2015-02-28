import logging
import pexpect
from time import sleep
import sys
from re import match, search, compile
import traceback

#######################################################################
# exceptions
#######################################################################

class ConnectorException( Exception ):
    def __init__( self, value ):
        self.value = value
    def __str__( self ):
        return repr( self.value )

class AccessException( ConnectorException ):
    pass
        
class NetworkException( ConnectorException ):
    pass
        
class TimeoutException( ConnectorException ):
    pass

class RemoteException( ConnectorException ):
    """ exception class for things like man-in-middle attack, remote connection closed etc """
    pass


#######################################################################
# Register connectors
#######################################################################


def get_connector( type, hostname, user, password, enable_password, port=None ):
    for c in Connector.__subclasses__():
        connector = c( hostname, user, password, enable_password, port=port )
        if connector.name == type:
            return connector
    raise Exception( 'Connector type %s not registered' % (type))


#######################################################################
# helper
#######################################################################

def onlyascii(char):
    if ord(char) < 48 or ord(char) > 127: return ''
    else: return char


#######################################################################
# connectors
#######################################################################

class Connector( object ):
    """
    a class to communicate with a device; should be attached to a network device class
    """

    name = 'connector'

    # session for the communication
    session = None

    # session variables
    host = None
    user = None
    password = None
    enable_password = None
    
    port = None
    
    # determine ansi escape sequences so we don't use them in the prompt
    ansisequence = compile(r'\x1B\[[^A-Za-z]*[A-Za-z]')

    timeout = 5

    def __init__( self, hostname, username, password, enable_password, port=None ):
        """ constructor """
        # create the ssh
        self.session = None # to be inheritied
        
        self.host = hostname
        self.user = username
        self.password = password
        self.enable_password = enable_password

        self.timeout = None
        
        self.options = None
        
        if not port == None:
            self.port = port

        # deal with initial setup questions
        self.wizard_responses = {}

    def __del__( self ):
        try:
            if hasattr( self, 'session' ):
                if hasattr( self.session, 'closed' ):
                    if not self.session.closed:
                        logging.debug("closing connector")
                        self.session.close( force=True )
                self.session.terminate( force=True )
        except KeyboardInterrupt, e:
            raise e
        except Exception, e:
            pass

    def interact( self, escape_character='\x1d'):
        return self.session.interact( escape_character=escape_character )
    
    def connect( self, prompt_postambles=['>'], login_timeout=None, options=None, empty_prompt=False, escape_prompt=True, prime=False, wizard_responses={}, **kwargs ):
        """ attempt to automatically determine the prompt with login """
        # logging.debug( str(self.name)+"'ing into host " + str(self.host) + ', user=' + str(self.user) ) #+ ", password=" + str(self.password)  )
        logging.debug( "%s'ing into host %s, user=%s, password=%s" % (self.name, self.host, self.user, self.password ) ) 

        # determine options
        these_options = self.options
        if not options == None:
            these_options = str(options)
        
        if login_timeout == None:
            login_timeout = self.timeout
        
        # spawn command
        _cmd = self.command( self.host, user=self.user, port=self.port, options=these_options, **kwargs )
        logging.debug( '  cmd: "' + _cmd + '", login timeout=' + str(login_timeout))

        max_tries = 2
        i = 0
        err = None
        while i < max_tries:
            try:
                logging.debug("trying connect (try %s/%s)..." %(i,max_tries) )
                self.session = pexpect.spawn( _cmd, timeout=login_timeout )        
                # try to connect, should raise an exception if fail
                if self.do_connect( success_prompt=prompt_postambles, timeout=login_timeout, prime=prime, wizard_responses=wizard_responses ):
                    logging.debug("done connect")
                    return True
                logging.debug('failed spawning')
            except AccessException, e:
                raise e
            except NetworkException, e:
                raise e
            except Exception, e:
                err = e
            finally:
                i = i + 1
            
        logging.debug('failed connect')
        raise ConnectorException, 'could not connect'

    def do_connect( self, success_prompt=['>'], timeout=8, prime=False, wizard_responses={} ):
        """ to be run immediately after pexpect has spawned """
        # create an array of regex responses
        responses = {
            '(?i)user(name)?:\s*$'             : self.enter_username,
            "(?i)password:\s*$"             : self.enter_login_password,
            "(?i)man\-in\-the\-middle"      : self.man_in_middle,
            "((?i)permission denied|^login: )": self.permission_denied,
            "(?i)connection closed by (remote|foreign) host":   self.connection_closed,
            "(?i)Could not resolve hostname (\w|\-|\.)+\: Name or service not known": self.no_resolve_hostname,
            "(?i)no route to host"          : self.no_route_to_host,
            "(?i) is not an open connection": self.connection_refused,
            "(?i) Connection refused"       : self.connection_refused,
            "(?i) Enter passphrase for key" : self.key_passphrase,
            "100\%":	self.done,
        }
        # add wizard questions
        for w in wizard_responses:
            self.wizard_responses[w] = wizard_responses[w]
            responses[w] = self.wizard_response

        # determine what we're waiting for
        expect = []
        action = []
        for k,v in responses.iteritems():
            expect.append( k )
            action.append( v )
        # add good!
        for p in success_prompt:
            expect.append( p )

        # logging.debug("expect: " + str(expect))

        i = 0 # arbitary
        last_i = None
        tries = 0
        max_tries = 3
        errors = 0
        max_errors = 1 #20 - bug with delegated login?
        logged_in = False
        
        err = None
        
        while logged_in == False and tries < max_tries:
            
            try:

                logging.debug(' prime: %s try: %s' % (prime,tries,))
                # send an initial carriage return
                if prime:
                    # for i in xrange(0,2):
                    self.sendline('')

                # wait for response
                i = self.session.expect( expect, timeout=timeout )
                res = self.get_buffer()
                logging.debug( "  got '%s' (%s/%s) prev output=%s" % (expect[i],i,len(responses.keys()),res) )
                
                # just do a check against the success prompt to what we got spat out
                if i >= len( responses.keys() ):
                    logged_in = True
                else:
                    # need to do something, use the returned i to determine what
                    logging.debug( "   running %s" % (action[i],) )
                    res = action[i]( prompt=expect[i], output=res, try_number=tries )
                    # hmmm... why not only count passwords?
                    if res:
                        tries = tries - 1 
                last_i = i


            except KeyboardInterrupt, e:
                raise e

            except pexpect.TIMEOUT:
                logging.debug( ' timed out (%s/%s)...'%(errors,max_errors))
                errors = errors + 1

                tries = tries - 1
                # sometimes this is due to the device already been logged on (eg configuring a new device)
                for i in xrange(0,2):
                    # TODO: interfers when the ssh output is not parsed correctly by session.exepct
                    # problem is that when we connect to an already open line (like a console), we need to send a few new lines to ensure it's open.
                    # logging.debug('  sending new line')
                    if prime:
                        self.sendline('')
                    sleep( 0.1 )
                if errors > max_errors:
                    raise TimeoutException( 'connection timed out' )
            except pexpect.EOF:                
                res = self.get_buffer()
                logging.debug("  EOF with '%s'" %(res))
                for r in responses:
                    logging.debug("    matching against " + str(r))
                    if search( r, str(res) ):
                        logging.debug( '    got %s' %(r))
                        responses[r]( try_number=tries )
                        logging.debug('    done...')
            except AccessException,e:
                err = e
                break
            except UserWarning, e:
                # it's fine, go ahead (eg scp)
                logged_in = True
            except Exception, e:
                # logging.debug("  unknown error: %s, %s" %(type(e),e))
                raise e


            # logging.error("HERE %s" % tries)
            tries = tries + 1

        if err:
            raise err
        return logged_in

    def enter_username( self, **kwarg ):
        # if last_i == i or authorisation_asked:
            # raise AccessException( 'access denied' )
        logging.debug('   entering username %s' %(self.user))
        self.sendline( self.user )
        # authorisation_asked = True    
        return True

    def enter_login_password( self, try_number=None, **kwargs ):
        logging.debug("    entering login password (try %s) %s" % (try_number,'') )
        if not try_number == None and try_number >= 1:
            logging.debug("    too many tries, assume failed")
            self.permission_denied()
        # logging.debug("** password=" + str(self.password))
        self.sendline( self.password )
    
    def man_in_middle( self, **kwarg ):
        raise RemoteException( 'possible man-in-the-middle attack' )

    def permission_denied(self, **kwarg ):
        raise AccessException( 'access denied' )

    # def terminal_type(self, **kwarg  ):
    #     # raise AccessException( 'remote host requested terminal type twice' )
    #     logging.debug("  entering terminal type")
    #     # 
    #     # self.session.sendline( terminal_type )

    def connection_closed( self, **kwarg ):
        raise AccessException( 'connection closed' )

    def no_resolve_hostname( self, **kwarg ):
        raise NetworkException( 'could not resolve hostname' )

    def no_route_to_host( self, **kwarg  ):
        raise NetworkException( 'no route to host' )

    def connection_refused( self, **kwarg  ):
        # this coudl just mean that the device doesn't support this connector method
        logging.debug("connection refused")
        raise AccessException( 'connection refused' )

    def key_passphrase( self, **kwargs ):
        self.session.sendline('')

    def wizard_response( self, prompt=None, output=None, **kwargs ):
        # logging.error("P: %s %s" % (prompt,self.wizard_responses))
        if prompt in self.wizard_responses:
            self.session.sendline( self.wizard_responses[prompt] )
            # logging.error("Q: %s > %s" % (prompt,self.wizard_responses[prompt]) )

    def done( self, **kwargs ):
        raise UserWarning('done')

    def disconnect( self ):
        """ cleanly disconnect from connection """
        # logging.debug("disconnect " + str(self.session) )
        if self.session == None:
            return None
        c = 0
        while self.session.isalive() and c < 4:
            logging.debug('  attempting disconnect')
            try:
                self.session.close( force=True )
                if self.session.isalive():
                    logging.debug( '  force terminate')
                    self.session.terminate( force=True )
            except Exception, e:
                logging.debug( ' something went wrong %s: %s' % (type(e),e))
                c = c + 1
        return
        
    def is_alive( self ):
        """ checks to ensure child process is alive """
        return self.session.isalive()
    
    def send( self, cmd ):
        """ send the command to the session """
        return self.sendline( cmd, carriage_return='' )

    def sendline( self, cmd, carriage_return="\x0d" ):
        """ send the command with carriage return at end """
        if self.is_alive():
            if cmd == None:
                cmd = ''
            # logging.debug("sendline: %s" % (cmd + carriage_return))
            return self.session.send( cmd + carriage_return )
        else:
            raise ConnectorException, 'connection is not alive!'
            
    def get_buffer( self ):
        """ retrieve the contents of the output buffer """
        # return self.session.before
        return self.session.before.replace('\r\n','\n').split("\n")
    
    def get_raw_buffer( self ):
        return self.session.buffer.replace('\r\n','\n').split("\n")

    def get_after_buffer( self ):
        return self.session.after.replace('\r\n','\n').split("\n")
    
    def get_match_buffer(self):
        return self.session.match
        
    def expect( self, array, timeout=-1 ):
        """ return the index of the matched entry from the array, with timeout """
        self.session.timeout = timeout
        i = None
        try:
            i = self.session.expect( array, timeout=timeout )
        except pexpect.TIMEOUT, e:
            raise TimeoutException( 'timed out waiting for command response' )
        return i


        
        

class SSH( Connector ):
    """ connector implementation for ssh """

    name = 'ssh'
    
    session = None
    port = 22

    def command( self, host, user=None, port=22, options=None, *args ):
        if options == {} or options == None:
            options = ''
        return "ssh -k -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no -p%s %s -l%s %s" % ( port, options, user, host )

    def options( self, string ):
        self.session.SSH_OPTS = string




class Telnet( Connector ):

    name = 'telnet'

    session = None
    port = 23

    def options( self, string ):
        self.session.OPTS = string

    def command( self, host, user=None, port=23, options=None, *args ):
        if options == None:
            options = ''
        return "telnet %s %s" % ( host, port )



class Screen( Connector ):
    """
    uses the screen command to connect to the serial port
    """
    
    name = 'screen'
    
    session = None
    port = '/dev/ttyS0'

    def options( self, string ):
        self.session.OPTS = string

    def connect( self, prompt_postambles=['>'], login_timeout=None, options=None, empty_prompt=None ):
        """ connect to device, and auto determine teh prompt """
        logging.debug( "screen'ing into host on port %s, user=%s', password=%s" % (self.port,self.user,self.password) )


        if not login_timeout:
            login_timeout = self.timeout

        # expected list of responses
        responses = [ \
                        'Username: ', #0 \
                        '(?i)password', #1 \
                        "((?i)Connection refused|\%Bad password)", #2 \
                        "(?i)connection closed by (remote|foreign) host", #3 \
                        "(?i)Name or service not known", #4 \
                        "(?i)no route to host", #5 \
                        "(?!)Name or service not known", #6 \
                        "(?!)Cannot open line", #7 \
                        # stuff on fresh switch
                        "Press RETURN to get started\!", #8
                        "Would you like to terminate autoinstall\?", #9 \
                        "Would you like to enter the initial configuration dialog\?", #10
                        pexpect.TIMEOUT, #10 \
                    ]
        # add the possible prompt postambles
        count = 0
        for p in prompt_postambles:
            responses.append( p )
            count = count + 1

        logging.debug("attempting connect to host on port %s" % (self.port) )

        # create a expect'd s screen
        _cmd = "screen %s" % self.port
        logging.debug( '  cmd: %s, login timeout=' % (_cmd,login_timeout) )
        self.session = pexpect.spawn( _cmd, timeout=login_timeout, env={ 'TERM': 'dumb' } )
        
        # need to wait a little, then send newline to get prompt
        sleep( 2 )

        # take action depending on what we get
        i = None
        last_i = None
        authorisation_asked = False
        initial_timeout = False
        while i < len(responses) - count:

            # let's get something from the line
            i = self.session.expect( responses )
            res = self.get_buffer()

            #logging.warn( "i=" + str(i) + ", RES: " + str(res) )
            logging.debug( "  connect subresult %s (%s)" %(i,responses[i]) )

            # monitor the response
            if i == 0:    # enter password
                if last_i == i or authorisation_asked:
                    raise AccessException( 'access denied' )
                self.session.sendline( self.user )
                authorisation_asked = True    

            elif i == 1:
                # make sure we only get asked once, if we get asked again, then the password has failed
                if last_i == i:
                    raise AccessException( 'access denied' ) 
                else:
                    self.session.sendline( self.password )
            elif i == 2:
                raise AccessException( 'connection refused' )
            elif i == 3:
                raise AccessException( 'access denied' )
            elif i == 4 or i == 6:
                raise NetworkException( 'could not resolve hostname' )
            elif i == 5:
                raise NetworkException( 'no route to host' )
                
            elif i == 7:
                raise NetworkException( 'could not attach to port' )

            elif i == 8:
                # started
                self.session.sendline( )
            elif i == 9:
                # terminate autoinstall
                logging.debug( "exiting autoinstall")
                self.session.sendline( 'yes' )
            elif i == 10:
                # terminate wizard
                self.session.sendline( 'no' )

            elif i == 11:
                if initial_timeout == False:
                    logging.debug( "sending cr")
                    self.session.sendline()
                    initial_timeout = True
                else:
                    raise TimeoutException( 'connection timed out' )

            last_i = i

        # screen now returns crap it the output for some reason...
        # return 'ap'
	# return 'Switch'
	return self._auto_discover_prompt( )

    def disconnect( self ):
        """ cleanly disconnect from connection """
        if self.session == None:
            return None
        logging.debug( "disconnect from screen")
        # make sure we reset the prompt
        self.session.sendline( 'end' )
        # now kill screen
        self.session.send( '\x01' )
        self.session.send(':kill')
        self.session.sendline()
        try:
            self.session.terminate( force=True )
        except:
            logging.debug( ' something went wrong')
            pass
        return True


class SCP( SSH ):
    """ connector for scp'ing files """
    name = 'scp'
    #def connect( self, remote_file=remote_file, local_file=local_file,  **kwargs ):
    #	return super( SCP, self ).connect( remote_file=remote_file, local_file=local_file, **kwargs )

    def command( self, host, **kwargs ):
        if kwargs['options'] == {} or kwargs['options'] == None:
            kwargs['options'] = ''
        if not 'frm' in kwargs and not 'to' in kwargs:
            raise ConnectorException('need to define frm and to file paths')
        return "scp -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no -p%s %s %s@%s:%s %s" % ( kwargs['port'], kwargs['options'], kwargs['user'], host, kwargs['frm'], kwargs['to'] )

