from netconfig.backup.configuration import Configuration



class CiscoTopspin( Configuration ):
    
    comment_matches = [
        # r'^!   TopspinOS',
        r'^!\s+(?P<last_change>.*)$',
    ]
    scrub_matches = [
        r'username guest community-string (?P<redact>.*)',
    ]
    
    # def getCommentLineInfo( self ):
    #     """ determines what lines we dont' really care about int eh config """
    #     # TODO: do something more intelligent?
    #     array = [1,2]
    #     logging.debug("  comment lines=" + str(array) )
    #     return array, None, None, None