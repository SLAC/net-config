from netconfig.backup.configuration import Configuration

from os import path, remove, devnull
import subprocess
import tempfile
import logging
import tarfile
from copy import deepcopy
from shutil import rmtree

class F5Tmsh( Configuration ):
    """
    ucs file is basically a tar.gz file
    in order to use them in net-config, we need to have a pointer to the filename and use set() point to it
    for comparision against another one, we should 
      a) uncompress the current version into a directory A
      b) uncompress the previous version into a directory B
      c) do a diff between the two directories, ignoring certain files that always change
    """

    scrub_matches = [
        r'(password|passphrase) (\S+) "(?P<redact>.*)"',
        r'\s+community name (?P<redact>.*)',
        r'\s+i(?P<redact>.*)_1',
    ]

    working_dir = None
    ignore_files = ( 'root/.tmsh-history-root', 'home/netmaint/.tmsh-history-netmaint', 'home/netmaint/.bash_history', 'home/netmon/.bash_history', 'home/netmon/.tmsh-history-netmon', 'SPEC-Manifest', 'SPEC-Files', 'var/lib/ntp/drift', 'etc/localtime' )

    def set( self, filename ):
        if not filename == None and path.isfile( filename ):
            self.working_dir = tempfile.mkdtemp()
            logging.debug("setting ltm configuration from %s using workdir %s" % (filename, self.working_dir))
            self._config = filename
            # unpackage this
            self.unpackage( filename, self.working_dir )
        else:
            raise Exception, 'no filename provided for configuration'

    def __del__( self ):
        # cleanup
        if self._config.startswith("/tmp/"):
            logging.debug("removing %s" % (self._config,))
            try:
                remove( self._config )
            except:
                pass
        if self.working_dir:
            logging.debug("cleaning up " + str(self.working_dir))
            try:
                rmtree( self.working_dir )
            except:
                pass

    def unpackage( self, ucs_file, dest ):
        logging.debug("unpacking tar %s to %s" %(ucs_file,dest))
        ucs = tarfile.open( ucs_file, 'r' )
        ucs.extractall( path=dest )
        # remove always changing files
        for f in self.ignore_files:
            try:
                logging.debug("  removing %s" % (dest+'/'+f,))
                remove( dest + '/' + f)
            except:
                pass
        for f in ( 'var/tmp', ):
            try:
                logging.debug("  removing %s" % (dest+'/'+f,))
                rmtree( dest + '/' + f )
            except:
                pass
        # logging.error("done")

    def get( self, ignore_meta=False, ignore_lines=[] ):
        return open( self._config, 'r' ).read()

    def dircmp( a, b ):
        diff = filecmp.dircmp( left, right )
        if len(diff.diff_files) > 0:
            return False
        return True
    
    def __str__(self):
        return '<F5TmshConfiguration object>'
        
    def __cmp__( self, configuration ):
        """ compares against another configuration """
        res = self.diff( configuration )
        return len(res)
        
    def contextual_diff( self, configuration, ignore_comments=False ):
        # logging.debug("CONTEXTUAL %s" % (configuration,))
        return self.diff( configuration, ignore_comments=ignore_comments )

    def diff( self, other, ignore_comments=False ):
        """ diff between two configuration objects as an array of strings """
        # TODO: ignore comments?
        try:
            logging.debug('   diff tmsh self: %s at %s, other: %s at %s' % (self, self.working_dir, other, other.working_dir ))
            left = self.working_dir
            right = other.working_dir
            cmd = 'diff -Naur %s %s' % (left,right)
            logging.debug("  running: %s" % (cmd,))
            res = []
            add = True
            with open(devnull, "w") as fnull:
                block = { }
                for i in subprocess.Popen( cmd.split(), stderr=fnull, stdout=subprocess.PIPE ).communicate()[0].split('\n'):
                    logging.debug("> %s" % (i,))
                    if i.startswith( 'diff ' ):
                        block['meta'] = None
                        block['diff'] = []
                        block['file'] = i.split()[-1].replace( right+'/', '' )
                    elif i.startswith('@@'):
                        if add and 'diff' in block and len(block['diff']) > 0:
                            res.append( deepcopy(block) )
                        add = True
                        block['meta'] = i
                    elif i.startswith( '--- ' ) or i.startswith( '+++ '):
                        continue
                    else:
                        if 'diff' in block:
                            # hack alert! we need to ignore the diffs of the last saved config time (as that will change always)
                            # we do this by checking other fields
                            if block['file'] == 'config/BigDB.dat' and i in ( ' display_name=Configsync.LocalConfigTime', ' display_name=LTM.ConfigTime' ):
                                logging.debug(" ignoring timestamps for config save")
                                add = False
                            block['diff'].append( i )
                    # logging.info(" + %s" % (block,))
                if add and 'diff' in block and len(block['diff']) > 0:
                    res.append( deepcopy(block) )
            # logging.debug( ' res: %s' % (res,))
            
            # double check to ensure we're ignoring files
            delete = []
            for i, r in enumerate(res):
                if r['file'] in self.ignore_files:
                    delete.append(i)
            # backwards
            for i in reversed( delete ):
                logging.debug('removing unwanted file diff at index %s' % i)
                res.pop(i)

            return res
        except Exception,e:
            logging.error("Error: %s %s" % (type(e),e))

        return []
