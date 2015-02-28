import argparse

from slac_utils.command import Command, CommandDispatcher
from slac_utils.logger import init_loggers
from slac_utils.util import get_array
from slac_utils.time import now, sleep
from datetime import timedelta

from netconfig import NewNetConfig as NetConfig
from netconfig.recipes.system import reload_and_monitor, FirmwareHelper, upgrade_firmware
from string import Template

from multiprocessing import Process
from slac_utils.queues import MultiprocessQueue


import sys
import logging


class FirmwareBase( Command ):
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        up = parser.add_argument_group('upgrade')
        up.add_argument( 'device', help='device to upgrade', nargs="+")

        up.add_argument( '-w', '--workers', help='number of concurrent workers', default=1 )

        up.add_argument( '-r', '--release', help='version to upgrade', default=None )
        up.add_argument( '-g', '--group', help='firmware group', default='production' )

        post = parser.add_argument_group('action')
        post.add_argument( '--reload', help='reload device after transfer', action='store_true', default=False )
        post.add_argument( '--dry_run', help='do not actually do the upgrade but show actions', action='store_true', default=False )
        
        fw = parser.add_argument_group('firmware')
        fw.add_argument( '--settings', default=settings )

    def setup( self, *args, **kwargs ):
        
        init_loggers( **kwargs )

        self.fw = FirmwareHelper( kwargs['settings'].server, kwargs['settings'].firmware )
        self.group = kwargs['group']
        self.release = kwargs['release']

        options = {}
        for i in ( 'profile', ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]
        self.netconfig = NetConfig( kwargs['config'] )   
        self.options = options


class Upgrade( FirmwareBase ):
    """
    upgrade device(s) to registered firmware versions
    """

    def run( self, *args, **kwargs ):

        self.setup( *args, **kwargs )

        # check to see if hosts is a file and determine appropriate argument array
        for d in get_array( kwargs['device'] ):
            device = self.netconfig.get( d, options=self.options )
            plan = upgrade_device( self.netconfig, device, self.group, self.release, self.fw, options=self.options, dry_run=kwargs['dry_run'] )
            if kwargs['reload']:
                for e in reload_and_monitor( self.netconfig, device, options=self.options, wait=900, delay=15 ):
                    if isinstance(e,str):
                        print "%s" % (e,)
                    else:
                        print
                        device = e

                # check version
                actual = {}
                # recast to something more useable
                for v in device.system.get():
                    logging.error("%s" % (v,))
                    if 'number' in v:
                        actual[v['number']] = v
                
                # match against plan
                for m in plan:
                    if 'number' in m:
                        stack = m['number']
                        if not m['to'] == actual[stack]['sw_version']:
                            logging.error("member %s is at incorrect firmware release: %s -> %s" % (stack,m,actual))
            
            

def firmware_worker( q, netconfig, group, release, fw, options, dry_run ):
    """
    worker wrapper for firmware tasks
    """
    print "report worker starting"
    while True:
        d = q.get()
        if d == None:
            q.task_done()
            break
        print "report worker working on %s" % (d,)
        device = netconfig.get( d, options=options )
        plan = upgrade_firmware( netconfig, device, group, release, fw, options=options, dry_run=dry_run )
        print "PLAN: %s %s" % (d,plan)
        q.task_done()
    print "report worker finished"

class Report( FirmwareBase ):
    """
    report on deviations for firmware versions
    TODO: something to report on what the standard mappings are
    """
    name = 'report'
    def run(self, *args, **kwargs):
        
        self.setup( *args, **kwargs )
        num_workers = int(kwargs['workers'])
        
        q = MultiprocessQueue()

        # multiprocess
        procs = []
        for i in range(num_workers):
            p = Process( target=firmware_worker, args=( q, self.netconfig, self.group, self.release, self.fw, self.options, True ) )
            p.daemon = True
            p.start()
            procs.append( p )
        
        
        # check to see if hosts is a file and determine appropriate argument array
        for d in get_array( kwargs['device'] ):
            q.put( d )
        
        # await all to be finished
        q.join()
        
        # clean up
        for i in range( num_workers ):
            q.put(None)
            

class Firmware( CommandDispatcher ):
    """
    Firmware related commands
    """
    commands = [ Upgrade, Report ]
