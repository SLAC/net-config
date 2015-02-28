import re
import getopt
import sys
import os
import getpass

import logging

def _parseArgs( args ):
    """
    these map key=argument, value=option value; if have = at end, then take in the argument
    """
    
    m = []
    options = {}

    getopt_short = ''
    getopt_long = []
    
    # construct the getops arguments
    for k in args.keys():
        n = []

        # long options
        if m.append( re.search( r'^--(.*)$', k ) ) or m[-1]:

            this = m[-1].group(1)
            options[this] = None

            if n.append( re.search( r'(\=)$', args[k] ) ) or n[-1]:
                if n[-1].group(1):
                    this = this + '='

            getopt_long.append(this)

        elif m.append( re.search( r'^-(.)$', k) ) or m[-1]:

            this = m[-1].group(1)
            options[this] = None

            if n.append( re.search( r'(\=)$', args[k]) ) or n[-1]:
                if n[-1].group(1):
                    this = this + ':'

            getopt_short = getopt_short + this
                    
    return getopt_short, getopt_long




def parseArgs( args ):
    """ given all the arguments, will work out what is an optional arg and normal arg """
    #logging.debug( "parsing arguments...")
    # parse the args list
    getopt_short, getopt_long = _parseArgs( args )
    #logging.debug( ' short: ' + str( getopt_short) )
    #logging.debug( ' long: ' + str( getopt_long ) )
    
    # do some reordering of the sys.args so that all options are in front
    optional = []
    required = []
    
    #logging.debug( "ALL: " + str(sys.argv[1:]) )
    #logging.debug( "input: " + str(args) )
    
    # do some analysis on input that requires a variable and are not just flags
    i = 1
    while i < len(sys.argv[1:]) + 1:
        s = sys.argv[i]
        #logging.debug( "looking at " + s )
        if re.match( '^\-', s ):
            optional.append( s )
            # check to see if option needs argument
            if args.has_key( s ):
                # if it ends in a '=' then, we need to reshuffle
                if args[s].endswith( '=' ):
                    next_item = sys.argv[i+1]
                    optional.append( next_item )
                    i = i + 1
        else:
            required.append( s )
        #logging.debug( "  got optional: " + str( optional ) + ", required: " + str( required ) )
        i = i + 1


    #logging.debug( 'parsed optional args: ' + str( optional ) + ", required args: " + str( required ) )

    parsed_args = {}
    try:
        opts, remain = getopt.getopt( optional, getopt_short, getopt_long )
        for i, a in opts:
            #logging.debug( "i " + i )
            for k in args.keys():
                if not k == i:
                    continue
                m = []
                name = args[k]
                #logging.debug( " key " + k )
                if m.append( re.search( r'^(.*)=$', args[k] ) ) or m[-1]:
                    name = m[-1].group(1)
                    #logging.debug( "  name to " + name )
                if a == '': a = True
                elif a == 'True': a = True
                elif a == 'False' or a == '0': a = False
                parsed_args[name] = a
                #logging.debug( "  setting options[" + name + "] to " + str(a) )

    except getopt.GetoptError, e:
        print "could not parse arguments: " + str( e )
        sys.exit(2)

    #logging.debug( 'parsed: ' + str(parsed_args) )

    return required, parsed_args



def parsePasswords( options, exclude=() ):
    """ simply reads the passwords if files are defined """
    # read in passwords from file
    for k in options:
        # logging.error("K: " + str(k))
        if re.search( 'password', k  ):
            # logging.error("  matched")
            if options[k]:
                try:
                    if not k in exclude and os.path.isfile( options[k] ):
                        # logging.warn( " --> " + k + " " + options[k] + ", " + getPassword( options[k] ) )
                        options[k] = getPassword( options[k] )
                except:
                    pass
    return options

def getArray( file ):
    """ given the file, reads in values and spits out the array """
    logging.debug( "input files: " + str(file))
    if file == "None" or file == '':
        return None
    f = []
    if not type(file) == list:
        f.append( file )
    else:
        f = file
    array = []

    # logging.error("determining f: " + str(f) + ", " + str(file))

    for i in f:
        try:
            f = open( i, 'r' )
            for l in f.readlines():
                # logging.error("L: " + str(l))
                h = l.rstrip()
                if not h == "":
                    array.append( h )
            f.close()
        except IOError, e:
            array.append( i )
    return array


def boolean( value ):
    """ given an input, returns whether it's true or false, or none """
    # logging.warn( "IN: '" + str( value ) + "'")

    if re.match( '(?i)y(es)?', str(value) ) or re.match( '(?i)t(rue)', str(value) ) or re.match( '(?i)e(nable)', str(value) ):
        return True
    elif re.match( '(?i)n(o)?', str(value) ) or re.match( '(?i)f(alse)', str(value) ) or re.match( '(?i)d(isable)', str(value) ):
        return False

    v = int( value )
    if v > 0:
        return True
    return False




def getUsername():
    """ get the username from teh environment """
    return getpass.getuser()


def getPassword( file ):
    """ 
    given the argument, determines if it's a file, and if it is will read it and spit out the 
    contents. if not, then will return the variable
    TODO: somethign with user input?
    """
    # logging.error("FILE: %s" % (file,))
    if file == "None" or file == '' or file == None:
        return None

    # TODO: check for permissions etc
    f = open( file )
    password = f.readline()
    f.close()
    password = password.rstrip()

    #logging.debug("password is " + password )
    return password


def getRTandComment( options ):
    """ scan options for the rt and comment, else ask for input """
    rt = None
    comment = None

    print
    print( "Please enter RT# and comments for this session (ctrl-c to ignore)")

    try:

        # ensure we have relevant comments and rt ref; ask if necessary
        if not options.has_key('rt'):
            # check environment
            if os.environ.has_key( 'NETCONFIG_RT' ):
                rt = os.environ['NETCONFIG_RT']
            else:
                # TODO: check for number only
                print " RT# ",
                this_rt = sys.stdin.readline()
                rt = this_rt.rstrip()

        if not options.has_key('comment'):

            # check os
            if os.environ.has_key( 'NETCONFIG_COMMENT' ):
                comment = os.environ['NETCONFIG_COMMENT']
            else:
                # look for double return to exit readline
                print "Comment: ",
                max_empty = 1
                empty = 0
                this_comment = ""
                while 1:
                    line = sys.stdin.readline()
                    if line == "\n":
                        empty = empty + 1
                        if empty >= max_empty:
                            break
                    else:
                        this_comment = this_comment + line

                this_comment.rstrip()
                comment = this_comment

    except KeyboardInterrupt:
        pass

    return rt, comment



def stripFQDN( hostname ):
    """ removes the domain name from the hostname """
    return hostname.lstrip('~/.').rsplit('/')[0].split('.')[0]


# def syncronized( method, mutex_finder=lambda x:x.mutex ):
#     """ ensure that the threaded class has a mutex self variable for locking """
#     def m(self, *args, **kargs):
#         mutex = mutex_finder(self)
#         logging.info("locking with " + str(mutex))
#         with mutex:
#             return method( self, *args, **kargs )
#     m.real_method = method
#     return m
