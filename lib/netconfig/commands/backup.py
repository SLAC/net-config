import argparse

from slac_utils.command import Command, CommandDispatcher, MultiprocessMixin
from slac_utils.logger import init_loggers
from slac_utils.util import get_array
from slac_utils.time import now, sleep
from datetime import timedelta

from netconfig import NewNetConfig as NetConfig
from netconfig.backup.storage import FileStore
from netconfig.backup.configuration import DeviceConfigurations
from string import Template

from multiprocessing import Process, Manager
from slac_utils.queues import MultiprocessQueue

from random import shuffle
import sys
import logging
import smtplib
import traceback
import os
import time
from pprint import pformat


def backup( hostname, netconfig_conf, mutex, storage_path, options, quiet, write_config, commit ):
    # logging.error("hostname: %s, netconfig=%s, storage=%s" % (hostname,netconfig_conf,storage_path))
    res, person, diff, error = None, None, {}, None
    device = None
    config = None
    if not quiet:
        logging.info("%s"%hostname)
    try:
        netconfig = NetConfig( netconfig_conf, mutex=mutex )
        storage = FileStore( path=storage_path )
        device = netconfig.get( hostname, options=options )
        netconfig.connect( device, **options )
        if commit:
            try:
                device.system.config.commit()
            except Exception,e:
                logging.info("%s: %s" % (hostname,e) )
                device.prompt.ask("", fail_okay=True)
        config = device.system.config.get()
        res, person, diff = storage.insert( hostname, config, commit=write_config )
    except Exception,e:
        logging.debug("Err: %s: %s\n%s" % (type(e),e,traceback.format_exc()) )
        error = str(e)
    finally:
        if device:
            device.disconnect()
    if not quiet:
        log = getattr( logging, 'info' )
        if error:
            log = getattr( logging, 'warn' )
        log("%s\t%s" % (hostname,{ 'changed': res, 'by': person, 'diff': diff, 'error': error }))
    return { 'changed': res, 'by': person, 'diff': diff, 'error': error, 'config': config }


def generate_changed( changed, width=80 ):
    if len(changed):
        yield ''
        yield '='*width
        yield  "The following hosts had changes in their configurations:"
        yield '='*width
        yield ''
        for host,data in changed.iteritems():
            for context,block in data['diff'].iteritems():
                yield '-'*width
                yield "%s - %s (%s)" % (host,context,data['by'] or 'unknown')
                yield '-'*width
                for b in block:
                    yield "%s" % b['meta']
                    for l in b['diff']:
                        yield l
            yield ''
        yield ''
    
def generate_errored( errored, width=80 ):
    if len(errored):
        yield ''
        yield '='*width 
        yield "The following hosts experienced errors whilst fetching their configurations:"
        yield '='*width
        yield ''
        for error,hosts in errored.iteritems():
            yield '-'*width
            yield error
            yield '-'*width
            for h in sorted(hosts):
                yield "%s" % h
            yield ''
        yield ''
    

def email( report, server, frm, subject, to=[] ):
    pre = [
        'From: ' + frm,
        'Subject: ' + subject,
        ''
    ]
    s = smtplib.SMTP(server)
    s.sendmail( frm, to, "\n".join( pre + report ) )


def disk( report, report_dirs, dir_format="%Y/%m", report_format="%Y-%m-%d_%H:%M.txt" ):
    # create report
    t = time.localtime()
    w = time.strftime( dir_format, t )
    for d in report_dirs:
        this = "%s/%s" % (d,w)
        if not os.path.exists( this ):
            os.makedirs( this )
        os.chdir( this )
        n = time.strftime( report_format, t )
        with open( n, 'w' ) as f:
            for r in report:
                f.write(r+"\n")

class ToFiles( Command, MultiprocessMixin ):
    """
    backup device configuration to files
    """
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( 'device', help='device(s) or file containing list of devices', nargs='+' )

        parser.add_argument( '-w', '--workers', help='number of concurrent workers', default=1, type=int )
        parser.add_argument( '-s', '--storage', help='storage_settings', default=settings.__dict__ )

        parser.add_argument( '--quiet', help='silent output', default=False, action="store_true" )

        parser.add_argument( '--commit', help='commit running config first on device', default=False, action="store_true" )

        parser.add_argument( '--randomise', help='randomise order of tests', default=False, action="store_true" )
        parser.add_argument( '--donotreport', help='hosts to ignore', default=[], nargs="*" )

        parser.add_argument( '--diffs_only', help='do not report errors', default=False, action="store_true" )

        parser.add_argument( '--email', help='who to email (sanitised) reports to', default=[], nargs="*" )
        parser.add_argument( '--report_dir', help='where to put reports', default=[], nargs="*" )
        
        parser.add_argument( '--file_store_path', help='path to config files root', default=settings['file_store']['path'] )

        parser.add_argument( '--log_format', default='%(module)s %(lineno)d\t%(levelname)s\t%(message)s', required=False )
        parser.add_argument( '--settings', default=settings, required=False )
        parser.add_argument( '--cache_group', default='backup' )


    def _run( self, write_config=True, **kwargs):

        init_loggers(**kwargs)

        num_workers = int(kwargs['workers'])
        options = {}
        for i in ( 'password', 'username', 'cache_group' ):
            if kwargs[i]:
                options[i] = kwargs[i]
        
        devices = get_array( kwargs['device'] )
        if kwargs['randomise']:
            shuffle(devices)

        # get lock
        manager = Manager()
        mutex = manager.Lock()
        
        # map/reduce
        target_args = [ kwargs['config'], mutex, kwargs['file_store_path'], options, kwargs['quiet'], True, kwargs['commit'] ]
        res = self.map( backup, devices, num_workers=kwargs['workers'], target_args=target_args )
        for hostname, status in self.fold( devices, res, ignore=kwargs['donotreport'] ):
            config = status['config']
            del status['config']
            yield hostname, config, status

        return

    def run(self, *args, **kwargs):

        errored = {}
        changed = {}
                    
        for hostname, config, status in self._run( write_config=True, **kwargs ):
            # don't bother if not changed
            if not status['changed'] == False:
                # organise by error
                if status['diff']:
                    changed[hostname] = status
                elif status['error']:
                    if not status['error'] in errored:
                        errored[status['error']] = []
                    errored[status['error']].append( hostname )
            
        changed_report = [ i for i in generate_changed( changed ) ]
        errored_report = [ i for i in generate_errored( errored ) ]
        
        # report on the diffs
        try:
            if len( changed_report ) or len(errored_report ):
                disk( changed_report + errored_report, kwargs['report_dir'] )
        except Exception, e:
            logging.error( "Could not write report to disk: (%s) %s" % (type(e),e) )

        if len( kwargs['email'] ):
            s = kwargs['settings']
            try:
                report = changed_report
                if not kwargs['diffs_only']:
                    report = report + errored_report
                if len(report ):
                    email( report, s['SMTP_SERVER'], s['FROM'], s['SUBJECT'], kwargs['email'] )
            except Exception, e:
                logging.error( "Could not send email: (%s) %s" % (type(e),e) )

class ToConsole( ToFiles ):
    """
    show device configuration to screen
    """
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( 'device', help='device(s) or file containing list of devices', nargs='+' )

        parser.add_argument( '-w', '--workers', help='number of concurrent workers', default=1, type=int )
        parser.add_argument( '--quiet', help='silent output', default=False, action="store_true" )

        parser.add_argument( '--commit', help='commit running config first on device', default=False, action="store_true" )
        
        parser.add_argument( '--randomise', help='randomise order of tests', default=False, action="store_true" )
        
        parser.add_argument( '--file_store_path', help='path to config files root', default=settings['file_store']['path'] )

        parser.add_argument( '--donotreport', help='hosts to ignore', default=[], nargs="*" )

        parser.add_argument( '--diff', help='do not report errors', default=False, action="store_true" )

        parser.add_argument( '--settings', default=settings, required=False )
        parser.add_argument( '--cache_group', default='backup' )


    def run(self, *args, **kwargs):

        for hostname, config, status in self._run( write_config=True, **kwargs ):
            if kwargs['diff']:
                print status['diff']
            else:
                print("%s" % (config,))


class Diff( Command, MultiprocessMixin ):
    """
    backup device configuration to files
    """
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( 'from', help='from config' )
        parser.add_argument( 'to', help='to config' )
        
        parser.add_argument( '-t', '--type', help='config format', choices=[ 'F5Tmsh', 'CiscoIos'], required=True )

        parser.add_argument( '-s', '--storage', help='storage_settings', default=settings.__dict__ )

        parser.add_argument( '--file_store_path', help='path to config files root', default=settings['file_store']['path'] )

        parser.add_argument( '--log_format', default='%(module)s %(lineno)d\t%(levelname)s\t%(message)s', required=False )
        parser.add_argument( '--settings', default=settings, required=False )


    def run( self, *args, **kwargs):

        init_loggers(**kwargs)
        
        frm = DeviceConfigurations( )
        config_class = frm.get_config_obj( kwargs['type'] )
        frm.setConfig( kwargs['from'], config_type=kwargs['type'] )
        
        to = DeviceConfigurations( )
        to.setConfig( kwargs['to'], config_type=kwargs['type'] )

        print pformat( frm.diff( to ) )


class Backup( CommandDispatcher ):
    """
    Configuration backup of device(s)
    """
    commands = [ ToFiles, ToConsole, Diff ]
