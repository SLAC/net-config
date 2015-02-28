#!/usr/local/bin/python

import logging
import sys
from re import sub, search
import time
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
import os
from multiprocessing import Process, Manager

from netconfig import NewNetConfig as NetConfig, config_file, util, parse_config
from slac_utils.command import Command, CommandDispatcher, MultiprocessMixin
from slac_utils.logger import init_loggers
from slac_utils.util import get_array

import traceback

def dumpPort( info ):
    logging.info("Port: %s" % (info,))
    # for i in [ 'port', 'state', 'trunk', 'vlan', 'autoneg', 'duplex', 'speed']:
    #     out = i
    #     if i == 'vlan':
    #         out = 'vlan#'
    #     if not i == 'alias':
    #         print( "   " + out + "\t" + str(info[i]) ) 



def compare( item, base, idx ):

    # logging.debug( "%s %s" % (item,base) )
    logging.debug("  baseline item: %s " % (idx))
    
    # some characteristics are booleans if disabled, dicts if enabled
    if isinstance( item, bool ) and isinstance( base, dict ):
        logging.debug("   dict: %s -> %s" % (item,base))
        yield idx
    
    else:
        # if dict, then follow down tree
        if isinstance( base, dict ):
            for i in base:
                if not i in item:
                    logging.debug("%s not in item %s" % (i,item))
                    yield idx
                else:
                    for c in compare( item[i], base[i], i ):
                        yield c

        # if list, then do diff on list items
        elif isinstance( base, list ):
            logging.debug("   list: %s -> %s" % (item,base))
            diff = set(base) - set(item)
            d = len(diff) == 0
            if not d:
                yield idx
        
        else:
        
            # deal with True base's when item is string, eg voice_vlan
            try:
                if not isinstance(item, bool):
                    item = float(item)
                    base = float(base)
            except:
                pass
            d = str(item) == str(base)
            if base == True and not isinstance(item,bool):
                d = True
            # logging.error("D: %s" % (d,))
            logging.debug("   string: %s -> %s\t(%s)" % (item,base,d) )
            if not d:
                yield idx

    return


def _compare_to_baseline( port, baseline, other_baselines=[] ):
    delta = {}
    logging.debug("compare\n%s\n%s" % (repr(port),baseline))
    for b in baseline:
        if not b in port:
            logging.debug("  %s is not defined" % (b,))
            # if we have None defined in the baseline, then fine
            if not baseline[b] == None:
                delta[b] = { 'configured': None, 'baseline': baseline[b] }
        else:
            if baseline[b] == None:
                logging.debug("  ignoring %s" % (b,))
            else:
                for i in compare( port[b], baseline[b], b ):
                    delta[b] = { 'configured': port[b], 'baseline': baseline[b] }
                    logging.debug( "  failed baseline: %s" % (i,))
                # logging.error(" >: %s" % (delta,))
    return delta


def compare_to_baselines( device, port, baselines, exceptions ):
    """
    determine the type of port and report the delta from defined baselines
    beware that in order to support priorities we have baselines as an array
    """
    possible_baselines = {}
    mapping = {}
    logging.debug("===== %s %s %s ======" % (device.hostname,port['port'],repr(port),))
    
    # check exceptions list fo rthis port
    if device.hostname in exceptions and port['port'] in exceptions[device.hostname]:
        delta =  _compare_to_baseline( port, exceptions[device.hostname][port['port']] )
        return 'EXCEPTED*', delta, True
    
    # how do we match the port to some baseline?
    # we use a context field in each baseline description to match the fields on our port
    for i,baseline in enumerate(baselines):
        
        for k,b in baseline.iteritems():
        
            logging.debug("Baseline: %s" % (k,))
            possible_baselines[k] = []
            mapping[k] = i
            # match up port fields against the baseline context's
            for context,value in b['context'].iteritems():
            
                # deal with special case of device name
                if context == 'device':
                    logging.debug(" TODO device %s" % (device,))
            
                elif context in port:
                
                    logging.debug(" context %s: port %s (%s), baseline %s (%s)" % (context,port[context],type(port[context]),value,type(value)))
                    this = port[context]
                    if not isinstance( port[context], list ):
                        this = [ port[context] ]

                    for t in this:
                        if isinstance( value, int ) or isinstance( value,bool ):
                            v = value == t
                        else:

                            if t == None:
                                t = ''
                            # logging.error("HERE: %s %s " % (value,t))
                            v = True if search( value, t ) else False
                        possible_baselines[k].append( v )

                else:
                    logging.debug(" context field %s not defined on port" % (context,))
                    possible_baselines[k].append( None )
                
            good = all( x == True for x in possible_baselines[k] )
            logging.debug( " => %s\t%s" % (possible_baselines[k], good) )
            if not good:
                # logging.error("DEL")
                del possible_baselines[k]
        
    matches = possible_baselines.keys()
    logging.debug("match: %s" % matches)
    # filter down
    found = None
    if len(matches) > 0:
        # deterine idx for each
        idx = None
        for m in matches:
            logging.debug(" m: %s %s %s" % (m, idx, found))
            if idx == None or mapping[m] < idx:
                idx = mapping[m]
                found = m
        if len(matches) > 1:
            logging.debug('many matching baseline profiles: %s, using first priority (%s)' % (matches,found) )
    elif len(matches) == 0:
        raise Exception, 'no matching baseline profiles'

    # unknown baseline    
    if not mapping[found] in baselines and not found in baselines[mapping[found]]:
        raise Exception, 'undefined baseline type %s' % (found,)

    def get_baseline( name ):
        return baselines[mapping[name]][name]['baseline']

    delta =  _compare_to_baseline( port, get_baseline(found), other_baselines=[ get_baseline(b) for b in matches ] )
    return found, delta, True if len(matches) else False



def port_baseline( hostname, netconfig_conf, mutex, interfaces, baselines, exceptions, options, fix, fix_only=None ):
    """
    if len(fix_only) == 0, assume fix all
    """

    device = None
    deltas = []
    
    if fix_only == None:
        fix_only = []
        
    try:
        
        logging.info('processing %s' % (hostname,))
        netconfig = NetConfig( netconfig_conf, mutex=mutex )
        device = netconfig.get( hostname, options=options )
        netconfig.connect( device, **options )
        device.prompt.terminal_buffer()

        # find all the ports
        ports = []
        if interfaces == None:
            ports = device.ports.filter()
        else:
            for i in interfaces:
                ports.append( device.ports.get( i ) )

        # do something with each port
        for p in ports:
        
            profile = None
            delta = {}
            multiple = False
            try:
                logging.info('analysing %s %s' % (hostname,p['port']))
                profile, delta, multiple = compare_to_baselines( device, p, baselines, exceptions )
            except Exception,e:
                logging.warn("%s\t%s: %s" % (hostname,p['port'],e))

            # logging.info("%-16s\t%-9s\t%26s%s\tdelta: %s" % (hostname, p['port'], profile, "*" if multiple else '', report_baseline_delta(delta),))

            fixed = False if len(delta.keys()) else None
            fix_this = True if len(fix_only) == 0 or profile in fix_only else False
            logging.debug(" fix: %s / %s" % (fix_this,fix_only))
            if profile and len(delta.keys()) and fix and fix_this:
                try:
                    logging.info('fixing %s %s with %s' % (hostname,p['port'],profile))
                    baseline = {}
                    for k,d in delta.iteritems():
                        if not 'baseline' in d:
                            raise Exception, 'profile %s does not contain a baseline stanza' % (profile,)
                        baseline[k] = d['baseline']
                    # always add the type to force cleaning of the configs
                    baseline['type'] = p['type']
                    baseline['port'] = p['port']
                    fixed, _tmp = device.ports.set( port=p, port_object=baseline, initial_check=False )
                except Exception,e:
                    logging.error("Err: %s\n%s" % ('could not fix %s' % p,traceback.format_exc()) )
            
            report = True
            if len(fix_only) and not profile in fix_only:
                report = False
                
            if report:
                deltas.append( {
                    'physical_port': p['port'],
                    'profile': profile,
                    'delta': delta,
                    'fixed': fixed
                } )

    except Exception,e:
        logging.error("Err: %s: %s\n%s" % (type(e),e,traceback.format_exc()) )
        error = str(e)
    finally:
        if device:
            device.disconnect()
    return { 'hostname': hostname, 'deltas': deltas }
            


def report_baseline_delta( delta ):
    logging.debug(" delta: %s" % (delta,))
    d = {}
    for k,v in delta.iteritems():
        if isinstance( v['baseline'], dict ):
            logging.debug("in dict: %s %s" % (k,v))
            d[k] = {}
            for i,w in v['baseline'].iteritems():
                logging.debug(" within %s %s" % (i,w))
                # deal with disabled dicts
                if isinstance( v['configured'], bool ):
                    d[k][i] = "%s [%s]" % ( v['configured'], w, )
                elif not i in v['configured']:
                    d[k][i] = "- [%s]" % (w,)
                elif not v['configured'][i] == w:
                    d[k][i] = "%s [%s]" % (v['configured'][i],w,)
                
        else:
            # logging.debug(">> %s (%s) %s" % (v['configured'],type(v['configured']),v['baseline']))
            value = []
            if isinstance( v['configured'], list ):
                value.append( v['baseline'] )
            else:
                value = v['baseline']
                
            # type of match?
            # logging.debug("in normal: %s %s %s (%s)" % (k,v['configured'],value,type(value)))
            if not value == v['configured']:
                d[k] = "%s [%s]" % (v['configured'],value)

    return d

def disk( report, report_dirs, dir_format="%Y/%m", report_format="%Y-%m-%d_%H:%M.yaml" ):
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
            dump( report, f, Dumper=Dumper)

class PortBaseline( Command, MultiprocessMixin ):
    """
    matches port configurations to baseline definitions
    """

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( '-q', '--quiet', help='silence output', default=False, action='store_true' )
        parser.add_argument( '-w', '--workers', help='number of concurrent workers', default=1, type=int )

        parser.add_argument( 'device', help='device to log onto', nargs='*' )
        parser.add_argument( '--baselines', help='baseline configuration', default=settings )

        parser.add_argument( '-i', '--interfaces', help='interface wildcard', action='append' )
        parser.add_argument( '-f', '--fix', help='make changes to port to fix baseline', action='store_true', default=False )
        parser.add_argument( '--fix_only', help='only fix ports matching defined baseline(s), default is all', action="append", nargs="*" )
        parser.add_argument( '-d', '--delta_only', help='reports deltas only', action="store_true", default=False )
        parser.add_argument( '--report_dir', help='where to put reports', default=[], nargs="*" )


    def run( self, *args, **kwargs ):
        init_loggers( **kwargs )
        
        options = {}
        for i in ( 'profile', 'port', 'prime', 'password', 'username' ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]

        report = {}

        # get lock
        manager = Manager()
        mutex = manager.Lock()

        devices = get_array( kwargs['device'] )
        
        fix_only = []
        if kwargs['fix_only']:
            fix_only = [ i[0] for i in kwargs['fix_only']]
            
        target_args = [ kwargs['config'], mutex, kwargs['interfaces'], kwargs['baselines']['BASELINES'], kwargs['baselines']['EXCEPTIONS'], options, kwargs['fix'], fix_only ]
        # logging.debug("TARGET: %s" % (target_args,))
        res = self.map( port_baseline, devices, num_workers=kwargs['workers'], target_args=target_args )
        for hostname, status in self.fold( devices, res ):
            for d in status['deltas']:
                fixed = '-'
                if d['fixed'] == True:
                    fixed = 'Y'
                elif d['fixed'] == False:
                    fixed = 'N'
                profile = d['profile']
                if profile == None:
                    profile = 'UNKNOWN'
                delta = report_baseline_delta(d['delta'])
                output = False if kwargs['delta_only'] == True and delta == {} else True
                if output:
                    print( "%-16s\t%-9s\t%26s\t%s\t%s" % (hostname, d['physical_port'], d['profile'], fixed, delta ))
                    if not hostname in report:
                        report[hostname] = {}
                    report[hostname][d['physical_port']] = {
                        'profile': d['profile'],
                        'delta': d['delta']
                    }
        
        disk( report, kwargs['report_dir'] )
