#!/usr/local/bin/python

import logging
import getopt
import sys
import string
import slac.netconfig
from slac.NetconfigDAO import *

first_line = 3
lines_to_print = 5

def parseArgs():
    """
    parses the system arguments to a consistent argument set
    """

    options = {
        'help': 0,
        'verbose': 0,
        'write':0,
        'import':'',
        'printcfg':0,
        'device':'',
        'ticket':0,
        'comment':'',
    }
    try:
        opts, args = getopt.getopt( sys.argv[1:],
                                   "hvwpi:d:t:c:", ["help", "verbose",\
                                   "write", "printconfigs", "import=",\
                                   "device=", "ticket=", "comment="])
        for o, a in opts:
            if o in ( "-h", "--help" ):
                options['help'] = 1
            elif o in ( '-v', '--verbose' ):
                options['verbose'] = 1
            elif o in ( '-w', '--write' ):
                options['write'] = 1
            elif o in ( '-i', '--import' ):
                options['import'] = a
            elif o in ( '-p', '--printconfigs' ):
                options['printcfg'] = 1
            elif o in ( '-d', '--device' ):
                options['device'] = a
            elif o in ( '-t', '--ticket' ):
                options['ticket'] = a
            elif o in ( '-c', '--comment' ):
                options['comment'] = a
            else:
                assert False, 'unhandled option' + str(o)

    except getopt.GetoptError, e:
        print str(e)
        sys.exit(2)

    return options

def printUsage():
    """ Function to print the usage options """
    """ dsneddon@slac.stanford.edu 20091030 """
    # Add options to shortoptions and optionsdesc for --help printout
    shortoptions = {
        'h':'help',
        'v':'verbose',
        'w':'write',
        'p':'printconfigs',
        'i':'import=<filename>',
        'd':'device=<devicename>',
        't':'ticket=<number>',
        'c':'comment="<comment>"',
    }
    optionsdesc = {
        'h':'Show usage and exit',
        'v':'Be verbose (print debugging messages)',
        'w':'Enable write access (turn off simulation mode)',
        'p':'Print the latest copy of the configs for all devices',
        'i':'Full path to config, no spaces (-i<filename>)',
        'd':'Explicitly declare device name (-d<devicename>)',
        't':'Include RT Ticket number (-t<number>)',
        'c':'Include quoted comment (-c"<comment>")',

    }
    print 'Usage: testsql sql_test [options...]'
    for k in shortoptions.keys():
        print '[-'+k+']',
        if shortoptions[k] != '':
            print '| [--'+shortoptions[k]+']',
        print '  '+optionsdesc[k]


def printDevices(qresult):

    def printDeviceHeader():
        print('/--------------------------------------------------------'
              '----------------------\\')
        print('|   ID   | Name                     | '
              'Version | DeviceType                     |')
        print('|--------------------------------------------------------'
              '----------------------|')

    def printDeviceFooter():
        print('\-------------------------------------------------------'
              '-----------------------/\n\n')

    print("Results Found from Device Table:")
    printDeviceHeader()
    for row in qresult.values:
        print "| " + str(str(row[0])).rjust(6) +" |",
        print str(str(row[1])).ljust(24) + " |",
        print str(sql.maxversion(str(row[0]))).ljust(7) + " |",
        print str(str(row[2])).ljust(30) + " |"
    printDeviceFooter()

def printConfig(config):
    def printConfigHeader():
        """ Print out table top and field IDs """
        print("/-----------------------------------------------------"
              "-------------------------\\")
        print("| Cfg ID [Ver]| [ ID ] Device                 | Updater  |"
              " Updated Date        |")

    def printConfigFooter():
        """ Print out a pretty end line for the results """
        print("\\-----------------------------------------------------"
              "-------------------------/")
        print

    def printConfigFields(configresult):
        """ Takes a config as a qresult and prints the data fields """

        for row in configresult.values:
            #for attribute in configresult:
                #logger.debug("configresult: ", dir(configresult))
            configId = str(row[0])
            #deviceId = str(configresult.values[1])
            deviceId = str(row[1])
            #deviceName = sql.getDeviceName(str(row[1]))
            deviceName = str(row[2])
            updatedBy = str(row[5])
            updatedDate = str(row[6])
            version = str(row[7])
            print "| "+configId.ljust(5)+"["+version.rjust(5)+"]|",
            print "["+deviceId.rjust(4) + "]",
            print deviceName.ljust(22) + " |",
            print updatedBy.ljust(8) + " |",
            print updatedDate.rjust(19) + " |"

    def printConfigText(configresult):
        """ Takes a config as a qresult and prints out the first few lines """
    #for device in deviceList.values:
            #logger.debug("device[0]: "+str(device[0]))
            #config = sql.getLatestConfig(str(device[0]))
        for row in configresult.values:
                #logger.debug("config.values: "+str(row[2]))
            configText = str(row[3])
            configList = configText.splitlines(0)
        for i in range(first_line, (first_line + lines_to_print)):
            try:
                print "| " + str(str(configList[i])).ljust(76) + " |"
            except IndexError:
                break
            #print configList[i]

    if config != None:
        printConfigHeader()
        printConfigFields(config)
        printConfigText(config)
        printConfigFooter()


def listDevices():
    result = sql.selectAllFromDevice()
    printDevices(result)
    return result

def listConfigs():
    result = sql.selectAllFromConfig()
    printConfigs(result)
    return result

def readConfigFileLocal(infile):
    """ Given a filename, open the file and return config """
    fh = slac.NetconfigDAO.fileHandler(options['verbose'])
    try:
        file = fh.openFile(infile)
    except:
        logger.info('Unexpected error: ' + repr(sys.exc_info()[1]))

    configLines = file.readlines()

def readfile(infile):
    """ read config and return list of lines in file """
    #_lines = []
    fh = slac.NetconfigDAO.fileHandler(options['verbose'])
    #logger.debug('_fh is of type:' + repr(_fh))
    #for attribute in dir(_fh):
        #    logger.debug(attribute)
    file = fh.readfile(infile)
    return file


if __name__ == "__main__":
    """ Parse arguments, then call testing functions as appropriate """
    # If no parameters supplied, print usage and exit
    if len(sys.argv[1:]):
        options = parseArgs()
    else:
        printUsage()
        sys.exit(2)

    # Initialize logging, at debug level if -v or --verbose specified
    if options['verbose']:
            logging.basicConfig(level=logging.DEBUG)

    logger=logging.getLogger("Sql_Test")
    logger.debug("Debug logging enabled")

    # Print options and exit if user specifies -h or --help
    if options['help']:
        printUsage()
        sys.exit(2)

    # Instantiate DB connection
    sql = slac.NetconfigDAO.sqlConnection(options['verbose'])

    # Enable writing to DB
    sql.writeEnable(options['write'])

    if options['printcfg']:
        # Print out the entire device table
        deviceList = listDevices()
        for device in deviceList.values:
            print sql.getDeviceName(str(device[0]))
            printConfig(sql.getLatestConfig(str(device[0])))

    if options['import'] != '':
        logger.debug('import=' + options['import'])
        sql.insertConfig(readfile(options['import']),options['import'],
                        None, options['ticket'], options['comment'])
        #insertConfig(readfile(options['import']))

    sys.exit(0)

