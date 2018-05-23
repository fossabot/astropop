# Licensed under a 3-clause BSD style license - see LICENSE.rst
import six
import numpy as np
from astropy.coordinates import Angle, SkyCoord, match_coordinates_sky


def match_indexes(ra, dec, cat_ra, cat_dec, limit_angle):
    '''Matches ra and dec lists coordinates with cat_ra and cat_dec coordinates
    from a catalog, within a limit angle.
    ra, dec, cat_ra, cat_dec are lists of decimal degrees floats
    limit_angle is string, float, `astropy.coordinates.Angle`, being the float
    a decimal degree and string a readable Angle.
    '''
    # # Matching using astropy's skycoord can be slow for big catalogs
    ind, dist, _ = match_coordinates_sky(SkyCoord(ra, dec, unit=('degree',
                                                                 'degree'),
                                                  frame='icrs'),
                                         SkyCoord(cat_ra, cat_dec,
                                                  unit=('degree', 'degree'),
                                                  frame='icrs'))

    index = np.zeros(len(ra), dtype=np.int)
    index.fill(-1)   # a nan index

    lim = Angle(limit_angle)
    for k in range(len(ra)):
        if dist[k] <= lim:
            index[k] = ind[k]

    return index


class _BaseCatalog():
    '''Base class for catalog query.'''
    # stores all the needed information to avoid continuous redundat queries
    _last_query_info = None
    _last_query_table = None
    comment = None

    def __evaluate__(self, center, radius=None, **kwargs):
        '''Query the results in the catalog.

        Parameters:
        -----------
            center : string or tuple
                The center of the search field.
                If center is a string, can be an object name or the string
                containing the object coordinates. If it is a tuple, have to be
                (ra, dec) coordinates, in hexa or decimal degrees format.
            radius : string, float, `astropy.coordinates.Angle`
                       or None (optional)
                The radius to search. If None, the query will be performed as
                single object query mode. Else, the query will be performed as
                field mode. If a string value is passed, it must be readable by
                astropy.coordinates.Angle. If a float value is passed, it will
                be interpreted as a decimal degree radius.
            ** kwargs
                other arguments to be passed to the catalog functions.
        '''
        if radius is None:
            return self.query_object(center, **kwargs)
        else:
            return self.query_region(center, radius, **kwargs)

    def _get_radius(self, radius):
        if isinstance(radius, six.string_types):
            radius = Angle(radius)
        if isinstance(radius, Angle):
            radius = radius.degree
        try:
            radius = float(radius)
            return radius
        except ValueError:
            raise ValueError("Radius value {} not understood.".format(radius))

    def _get_center(self, center):
        raise NotImplementedError("Resolve the center of the query is not "
                                  "supported by this catalog.")

    def query_object(self, center, **kwargs):
        raise NotImplementedError("This catalog does not support object mode"
                                  " query")

    def query_region(self, center, radius, **kwargs):
        raise NotImplementedError("This catalog does not support region mode"
                                  " query")

    def flush(self):
        '''Clear previous query informations.'''
        self._last_query_info = None
        self._last_query_table = None


class _BasePhotometryCatalog(_BaseCatalog):
    '''A base class for photometry catalogsself.

    Parameters:
    -----------
        name : string
            A name to designate the catalog.
        type : 'online' or 'local'
            If the catalog is online.
        flux_unit : 'mag', 'log' or 'linear'
            The unit of the data sotred as flux in catalog. Can be `linear`,
            corresponding to a linear flux scale, `mag` for magnitudes or `log`
            for log10(flux) scales.
    '''
    name = None
    type = None
    flux_unit = None
    available_filters = []
    bibcode = None

    def check_filter(self, filter, raise_error=True):
        '''Check if a filter is available for this catalog.'''
        if not raise_error:
            return filter in self.available_filters
        elif filter not in self.available_filters:
            raise ValueError('This catalog does not support {} filter. '
                             'The available formats are: {}'
                             .format(filter, self.available_filters))

    def query_ra_dec(self, center, radius, **kwargs):
        """Query coordinates in a region of the catalog."""
        raise NotImplementedError("This catalog does not support coordinates"
                                  " query mode")

    def query_flux(self, center, radius, **kwargs):
        """Query the flux data in a region of the catalog."""
        raise NotImplementedError("This catalog does not support coordinates"
                                  " query mode")

    def query_id(self, center, radius, **kwargs):
        """Query coordinates in a region of the catalog."""
        raise NotImplementedError("This catalog does not support coordinates"
                                  " query mode")

    def match_objects(self, ra, dec, limit_angle='2 arcsec'):
        '''Query the informations in the catalog from a list of ra and dec
        coordinates, matching the stars by a limit_angle.
        '''
        raise NotImplementedError("This catalog does not support object"
                                  " matching.")