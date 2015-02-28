from netconfig.backup.configuration import Configuration

class BluecoatSg( Configuration ):

    stanza_prefix = None
    
    comment_matches = [
        r'^\!- ',
        r'^inline (exceptions|wccp\-settings) end\-\d+\-inline',
        r'end\-\d+\-inline(-xml)?',
        r'\-\-\w+\.\w+\-\-',
    ]
    
    scrub_matches = [
    ]
    
    # def getCommentLineInfo( self ):
    #     """ determines the line numbers which correspond to the configuration update/saved comments; note it counts from 0 """
    #     array = []
    #     m = []
    #     last_change = None
    #     last_save = None
    #     by = None
    #     i = 0
    #     logging.debug( "determining comment lines in config" )
    #     for l in self._config:
    # 
    #         if re.match( r'^\!- ', l ):
    #             logging.debug( "  found comment line" )
    #             array.append( i )
    # 
    #         elif re.search( r'^inline (exceptions|wccp\-settings) end\-\d+\-inline', l ):
    #             logging.debug( "  found inline crap" )
    #             array.append( i )
    # 
    #         elif re.search( r'end\-\d+\-inline(-xml)?', l ):
    #             logging.debug( "  found end inline crap" )
    #             array.append( i )
    # 
    #         elif re.search( r'\-\-\w+\.\w+\-\-', l ):
    #             logging.debug( "  found funny marker line" )
    #             array.append( i )
    # 
    #         i = i + 1
    # 
    #     logging.debug("  ignore lines = " + str(array) + ', changed=' + str(last_change) + ', save=' + str(last_save))
    #     return array, last_change, last_save, by
