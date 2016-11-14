'''
Created on May 8, 2016

@author: Martin Vo
'''

from utils.commons import returns,accepts
from stars_processing.filters_tools.base_filter import BaseFilter, Learnable
from entities.exceptions import QueryInputError

class ColorIndexFilter(BaseFilter, Learnable):
    '''
    Filter star according their color indexes    
    '''

    def __init__(self, colors = ["b_mag", "v_mag", "i_mag"],
                 decider = None, pass_not_found = False, raise_if_not = False,
                 plot_save_path = None, plot_save_name = "",
                 without_notfound = False, *args, **kwargs):
        '''
        Parameters:
        -----------
            colors : list of strings
                List of magnitudes which will be used. They are keys to color indexes
                in star's object attribute 'more', where can be stored anything 
        
            decider : Decider object
                Instanced decider object which is able to be learned on train sample
                
            pass_not_found : bool 
                If False stars without color index will be denied 
                
            raise_if_not : bool
                If True it throws exception whenever a star has no color index
                
            plot_save_path : str, NoneType
                Location for saving plot of probabilities after learning. If None,
                plot will not be saved, but showed
                
            without_notfound : bool
                If False coordinates of stars which have no color indexes will
                be returned as well, but with None instead of coordinates (list of
                values)
                
        '''
        self.decider = decider
        self.pass_not_found = pass_not_found
        self.colors = colors
        self.labels = self.colors

        
        self.raise_if_not = raise_if_not
        
        self.plot_save_path = plot_save_path
        self.plot_save_name = plot_save_name
        
        self.without_notfound = without_notfound
    
    @accepts(list)
    @returns(list)     
    def applyFilter(self, stars ):
        stars_coords = self.getSpaceCoords( stars )    
        
        stars_without_colors = []
        stars_with_colors = []
        coords_with_colors = []
        for i, coo in enumerate(stars_coords):
            if coo == None:
                stars_without_colors.append( stars[i] )
            else:
                coords_with_colors.append( coo )
                stars_with_colors.append( stars[i] )
                   
        passed = self.decider.filter( coords_with_colors )
        
        add_stars = []
        if self.pass_not_found == True:
            add_stars = stars_without_colors            
        
        return [ star for this_passed, star in zip( passed, stars_with_colors) if this_passed == True] + add_stars
    
    
    def getSpaceCoords(self, stars):  
        """
        Get list of desired colors
        
        Parameters:
        -----------
            stars : list of Star objects
                Stars with color magnitudes in their 'more' attribute
 
        Returns:
        -------
            List of list of floats
        """
        coords = []
        
        for star in stars:    
            colors = []
            for col in self.colors: 
                if not "-" in col:       
                    colors.append( star.more.get( col , None ) )
                else:
                    try:
                        mag1_txt, mag2_txt = col.split("-")
                        mag1, mag2 = star.more.get( mag1_txt.strip() , None ), star.more.get( mag2_txt.strip() , None ) 
                        if mag1 and mag2:
                            col_index = mag1 - mag2 
                        else:
                            col_index = None
                        
                        colors.append( col_index )
                    except:
                        raise QueryInputError("Invalid color index input.\nThere have to be mag1-mag2.")
           
            if not None in colors:
                coords.append( [ float(c) for c in colors] )  
            else:
                
                if self.raise_if_not:
                    raise Exception("Star %s has no color index." % star.ident)
                
                if not self.without_notfound:
                    coords.append( None )

        return coords  

        