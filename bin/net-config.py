#!/usr/bin/python

from __future__ import absolute_import

import sys
from os import path as path
import argparse

parent = lambda x: path.split(x)[0] if path.isdir(x) else split(path.dirname(x))[0]
app_path = path.dirname( path.realpath(__file__) )

# add ../lib to path
lib_path = parent( app_path ) + '/lib/'
sys.path = [ lib_path ] + sys.path
# add conf path
conf_path = parent( app_path ) + '/etc/net-config/'

from slac_utils.command import execute_command

from netconfig import config_file

import traceback

CMD_MAP = {
    
    'edit': {
        'klass': 'netconfig.commands.edit.Edit',
    },
    'pipe': {
        'klass': 'netconfig.commands.pipe.Pipe',
    },
    'firmware': {
        'klass': 'netconfig.commands.firmware.Firmware',
        'conf': conf_path + 'firmware.yaml'
    },
    'reload': {
        'klass': 'netconfig.commands.reload.Reload',
    },
    'backup': {
        'klass': 'netconfig.commands.backup.Backup',
        'conf': conf_path + 'backup.yaml'
        
    },
    'port_baseline': {
        'klass': 'netconfig.commands.port_baseline.PortBaseline',
        'help': 'Port baseline auditor',
        'conf': conf_path + 'port_baseline.yaml'
    },
    'management': {
        'klass': 'netconfig.commands.management.Management',
    },
    'wireless': {
        'klass': 'netconfig.commands.wireless.Wireless',
        'conf': conf_path + 'firmware.yaml'
    },
    'interface': {
        'klass': 'netconfig.commands.interface.Interface',
    },
    'api': {
        'klass': 'netconfig.commands.api.Api',
    },
    # 'netconf': {
    #     'klass': 'netconfig.commands.netconf.NetConf'
    # }
    'stage': {
        'klass': 'netconfig.commands.stage.Stage',
        'conf': [ conf_path + 'staging.yaml', conf_path + 'firmware.yaml' ]
    },
    'configs': {
        'klass': 'netconfig.commands.configs.Configs',
    },
        

}


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser( description='api for network devices', conflict_handler='resolve', add_help=False ) 
    parser.add_argument( '-v', '--verbose', help='verbose output', action='store_true', default=False )
    parser.add_argument( '-c', '--config', help='configuration file', default=conf_path + 'net-config.yaml' )
    # parser.add_argument( '-f', '--profile', help='force driver', default=None )
    parser.add_argument( '-p', '--password', help='password', default=None )
    parser.add_argument( '-u', '--username', help='username', default=None )

    try:
        execute_command( CMD_MAP, parser, *sys.argv )
    except Exception, e:
        t = traceback.format_exc()
        print "Err: (%s) %s\n%s" % (type(e),e,t)
