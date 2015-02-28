#!/usr/local/bin/python

import logging
import getopt
import sys

import slac.subversionclient

Url = None

def usage():
	print "Tests the pysvn libraries"
	print "Usage: "

def printRepositoryUrl ( path ):
	""" get the URL of the repository at the given path """
	try:
		# get the URL of the repository
		Url = slac.subversionclient.getRepositoryUrl(path)
		print 'Url:', Url

	except Exception, e:
		logging.error( str(e) )

if __name__ == "__main__":

	# parse arguments
	options = slac.subversionclient.parseArgs()

	# logging
	if options['verbose'] == 1:
		logging.basicConfig(level=logging.DEBUG)

	if options['help'] == 1:
		usage()
		sys.exit()

	# print repository URL
	printRepositoryUrl(options['path'])
	#printRepositoryUrl( '.' )

