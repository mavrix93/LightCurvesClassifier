'''
Created on May 8, 2016

@author: Martin Vo
'''

from utils.commons import returns,accepts
from stars_processing.filters_tools.base_filter import BaseFilter

class ColorIndexFilter(BaseFilter):
    '''
    Filter star according their color indexes    
    '''

    def __init__(self, colors = ["b_mag", "v_mag", "i_mag"],
                 decider = None, pass_not_found = False, raise_if_not = False,
                 save_plot_path = None, *args, **kwargs):
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
                
            save_plot_path : str, NoneType
                Location for saving plot of probabilities after learning. If None,
                plot will not be saved, but showed
                
        '''
        self.decider = decider
        self.pass_not_found = pass_not_found
        self.colors = colors
        
        self.raise_if_not = raise_if_not
        
        self.save_plot_path = save_plot_path
    
    @accepts(list)
    @returns(list)     
    def applyFilter(self, stars ):
        stars_coords = self.getColorCoords( stars )    
        
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
    
    
    def getColorCoords(self, stars, without_notfound = False):  
        """
        Get list of desired colors
        
        Parameters:
        -----------
            stars : list of Star objects
                Stars with color magnitudes in their 'more' attribute
                
            without_notfound : bool
                If False coordinates of stars which have no color indexes will
                be returned as well, but with None instead of coordinates (list of
                values)
                
        Returns:
        -------
            List of list of floats
        """
        coords = []
        
        for star in stars:    
            colors = []
            for col in self.colors:        
                colors.append( star.more.get( col , None ) ) 
           
            if not None in colors:
                coords.append( [ float(c) for c in colors] )  
            else:
                
                if self.raise_if_not:
                    raise Exception("Star %s has no color index." % star.ident)
                
                if not without_notfound:
                    coords.append( None )
        
        return coords  

    
    def learn(self, searched_stars, contamination_stars):        
        self.decider.learn( self.getColorCoords( searched_stars, without_notfound = True),
                            self.getColorCoords(contamination_stars, without_notfound = True))
        
        if len(self.colors) == 2:
            self.decider.plotProbabSpace( save_path = self.save_plot_path)
            
        
        