import pxssh
import getpass

import logging


def get_password( file ):
    f = open( file )
    password = f.readline()
    f.close()
    password = password.rstrip()
    #logging.debug("password is " + password )
    return password



class NetworkDeviceConnector:
    """ a simple wrapper for ssh'ing into a cisco device """

    def __init__( self, host, user, password, enable_password ):
        logging.debug("creating NetworkDeviceConnector")

        # create the ssh
        self.session = pxssh.pxssh()

        # params
        self.host = host
        self.user = user
        self.password = password
        self.enable_password = enable_password
        
        self.session.UNIQUE_PROMPT = "[\>]"
        self.session.PROMPT = self.session.UNIQUE_PROMPT

        self.any_prompt = "(\>|\#)"
        self.any_normal_prompt = "(swh|rtr)\-.*\>"
        self.any_enable_prompt = "(swh|rtr)\-.*\#"

        self.config_prompt = "(swh|rtr)\-.*\(config\)\#"
        self.any_config_prompt = "(swh|rtr)\-.*\(config\-.*\)\#"
        self.if_config_prompt = "(swh|rtr)\-.*\(config\-if\)\#"
        
    
    def host( self, host ):
        self.host = host;
        
    def user( self, user ):
        self.user = user
        
    def password( self, password ):
        self.password = password
        
    def enablePassword( self, password ):
        self.enable_password = password
    
    def connect( self ):
        logging.debug("login into " + self.host)
        status = self.session.login( self.host, self.user, self.password, login_timeout=5 )
        logging.debug( "logged in: " + str(status) );
        return status


    def disconnect( self ):
        """ cleanly disconnect from connection """
        logging.debug('sending disconnect...')
        self.enableMode()
        self.session.sendline( 'exit' )

        return self.session.logout()


    def send( self, command ):
        logging.debug( "running command '" + command + "'...")
        self.session.sendline( command )
        # deal with long outputs with space
        i = 0
        output = ''
        while( i == 0 ):

            i = self.session.expect( [ ' --More-- $', self.any_prompt ] )
            output = output + self.session.before
            if ( i == 0 ):
                self.session.send( '\x20' ) # space char
            
        return output

    def sendMany( self, array ):
        logging.debug( "running many commands...")
        total_output = ''
        for l in array:
            output = self.send( l )
            total_output += output
        return total_output


    
    def enableMode( self ):
        """ sets to top level enable mode """
        
        logging.debug( "entering enable mode...")
        ok = False
        
        while not ok:

            logging.debug('sending enable...')
            self.session.sendline( 'enable' )
            i = self.session.expect( [ 'Password:', self.config_prompt, self.any_config_prompt, self.any_enable_prompt ] )

            logging.debug( "  got enable " + str(i))

            # enter the enable pasword
            if i == 0:
                self.session.sendline( self.enable_password )
                j = self.session.expect( [ self.any_enable_prompt ] )
                if j == 0:
                    ok = True
                    
            # in some config mode      
            elif i == 1 or i == 2:
                logging.debug( "  sending exit")
                self.session.sendline( 'exit' )
                j = self.session.expect( [ self.any_config_prompt, self.any_enable_prompt ])
                logging.debug( "    got exit " + str( j ) )
                if j == 0:
                    ok = False
                elif j == 1:
                    ok = True

            # already in enable mode
            elif i == 3:
                ok = True
                
            else:
                logger.error( "unknown expect from enable " . self.session.before )
                
                
        return ok


    def configMode( self ):
        """ sets up the connection to be in top level configure terminal mode """
        
        logging.debug( "entering config term mode")
        # go into top level enable mode
        self.enableMode()
        
        self.session.sendline( 'conf term')
        i = self.session.expect( [self.config_prompt, self.any_config_prompt] )
        logging.debug( "  got config " + str(i) )
        if i == 0:
            return True
        elif i == 1:
            self.session.sendline( 'exit' )
            j = self.session.expect( [ self.config_prompt ])
            if j == 0:
                return True
            else:
                logger.error( "unknown expect from config exit " . self.session.before )
                
        return False



    def commit( self ):
        """ write mem """
        logging.debug("committing to nvram")
        self.enableMode()
        self.session.sendline('write mem')
        i = self.session.expect( [ '\[OK\]' ], timeout=15 ) # writing config can be long, what failures?
        logging.debug( "  got " + str(i) )
        if i == 0:
            return True
        else:
            logging.error( "could not commit configuration")
            return False;


    def getRunningConfiguration( self ):
        """ gets the current running configuration """
        logging.debug( "getting configuration")
        self.enableMode()
        return self.send("show run")
        

# logging
logging.basicConfig(level=logging.DEBUG)

login_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password'
enable_password_file = '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/enable.password'

hostname = 'swh-ibfarmcore1.slac.stanford.edu'
username = 'super'
password = get_password( login_password_file )
enable_password = get_password( enable_password_file )

try:

    # create session to device
    session = NetworkDeviceConnector( hostname, username, password, enable_password )
    session.connect( )
    
    # get the verison
    logging.info( "--------")
    logging.info( session.getRunningConfiguration() )
    logging.info( "--------")

    session.disconnect()

except Exception, e:

    print "pxssh failed on login."
    logging.error( str(e) )

    