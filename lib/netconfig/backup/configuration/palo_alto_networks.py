from netconfig.backup.configuration import Configuration

class PaloAltoNetworks( Configuration ):
    scrub_matches = [
        r'phash (?P<redact>.*)',
    ]
