# Licensed under a 3-clause BSD style license - see LICENSE.rst
'''
Astrometry.net

This module wraps the astrometry.net solve-field routine, with automatic
improvements.
'''


import os
import sys
import shutil
import subprocess
import copy
from tempfile import NamedTemporaryFile, mkdtemp

import numpy as np

from astropy.io import fits
from astropy.wcs import WCS

from .coords_utils import guess_coordinates
from ..logger import logger
from ..math.opd_utils import solve_decimal


__all__ = ['AstrometrySolver', 'solve_astrometry_xy', 'solve_astrometry_image',
           'create_xyls', 'AstrometryNetUnsolvedField']


class AstrometryNetUnsolvedField(subprocess.CalledProcessError):
    """ Raised if Astrometry.net could not solve the field """
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return "{0}: could not solve field".format(self.path)


class AstrometrySolver():
    """Use astrometry.net to solve the astrometry of images or list of stars.
    For convenience, all the auxiliary files will be deleted, except you
    specify to keep it with 'keep_files'.
    """
    def __init__(self, astrometry_command=shutil.which('solve-field'),
                 defaults={'no-plot': None, 'overwrite': None},
                 keep_files=False):
        self._command = astrometry_command
        self._defaults = defaults
        self._keep = keep_files

    def _guess_coordinates(self, header, ra_key, dec_key):
        '''
        Guess the center coordinates of field based in header keys.
        '''
        ra = solve_decimal(str(header[ra_key]))
        dec = solve_decimal(str(header[dec_key]))

        return guess_coordinates(ra, dec)

    def _guess_field_params(self, header, image_params):
        """Guess the approximate field parameters from the header.

        The estimated parameters are:
            coordinates : 'ra' and 'dec'
            plate scale : 'scale-units', 'scale-high', 'scale-low'
        """
        options = {}
        keys = image_params.keys()
        if 'ra' in keys and 'dec' in keys:
            try:
                ra = float(image_params.get('ra'))
                dec = float(image_params.get('dec'))
                logger.info("Usign given field coordinates: {} {}".format(ra,
                                                                          dec))
                options['ra'] = ra
                options['dec'] = dec
            except ValueError:
                logger.warn('Could not convert field coordinates to decimal'
                            ' degrees. Ignoring it: {}{}'.format(ra, dec))
        elif 'ra_key' in keys and 'dec_key' in keys:
            logger.info("Figuring out field center coordinates")
            try:
                coords = self._guess_coordinates(header,
                                                 image_params.get('ra_key'),
                                                 image_params.get('dec_key'))
                options['ra'] = coords.ra.degree
                options['dec'] = coords.dec.degree
            except KeyError as e:
                logger.warn("Cannot understand coordinates in FITS header")
        else:
            logger.warn("Astrometry.net will try to solve without the field"
                        " center")

        if 'pltscl' in keys:
            try:
                pltscl = float(image_params.get('pltscl'))
                logger.info("Usign given plate scale: {}".format(pltscl))
            except ValueError:
                logger.warn('Plate scale value not recognized.'
                            ' Ignoring it. {}'.format(pltscl))
        elif 'pltscl_key' in keys:
            logger.info("Figuring out the plate scale from FITS header")
            try:
                pltscl = header[image_params.get('pltscl_key')]
                pltscl = float(solve_decimal(pltscl))
            except KeyError:
                logger.warn("Cannot understand plate scale in FITS header")
        try:
            options['scale-high'] = 1.1*pltscl
            options['scale-low'] = 0.9*pltscl
            options['scale-units'] = 'arcsecperpix'
        except NameError:
            logger.warn('Astrometry.net will be run without plate scale.')

        if 'ra' in options.keys():
            if 'radius' in keys:
                options['radius'] = float(image_params.get('radius', 1.0))
            else:
                options['radius'] = 1.0

        return options

    def solve_field(self, filename, output_file=None, wcs=False,
                    image_params={},
                    solve_params={}, scamp_basename=None,
                    show_process=False):
        """Try to solve an image using the astrometry.net.

        The image params can be:
            'ra_key' : header key for RA
            'dec_key' : header key for DEC
            'pltscl_key' : header key for plate scale
            'ra' : approximate center of the image in RA in decimal degrees
            'dec' : approximate center of the image in DEC in decimal degrees
            'pltscl' : plate scale of the image in arcsec/px
            'radius' : maximum radius to search around the center

        The solve_params are additional parameters that will be passed to
        solve-filed command. They can be:
            'no-fits2fits', 'overwrite', 'depth', 'no-plot', etc.

        'hdu' defines the number of the HDU to be solved, generally 0 (first)
        for images.

        Returns:
        --------
        header : `astropy.io.fits.Header` or `astropy.wcs.WCS`
            A header containing the solved wcs of the field and another
            information from astrometry.net. If return_wcs=True, a WCS
            object will be returned.
        """
        options = copy.copy(self._defaults)
        options.update(solve_params)

        if scamp_basename is not None:
            options['scamp-ref'] = scamp_basename + ".ref"
            options['scamp-config'] = scamp_basename + ".scamp"
            options['scamp'] = scamp_basename + ".cat"

        if output_file is not None:
            options['new-fits'] = output_file

        try:
            field_params = self._guess_field_params(fits.getheader(filename),
                                                    image_params=image_params)
        except (OSError, IOError):
            logger.warn('Could not guess field center and plate scale. '
                        'Running in slow mode.')
            field_params = {}
        options.update(field_params)

        if show_process:
            fd = sys.stdout
        else:
            fd = open(os.devnull, 'wb')

        solved_header = self._run_solver(filename, stdout=fd, stderr=fd,
                                         params=options)

        if not wcs:
            return solved_header
        else:
            return WCS(solved_header, relax=True)

    def _run_solver(self, filename, params, output_dir=None,
                    stdout=None, stderr=None):
        """Run the astrometry.net localy using the given params.

        STDOUT and STDERR can be stored in variables for better check after.
        """
        basename = os.path.basename(filename)
        root, ext = os.path.splitext(basename)
        if output_dir is None:
            output_dir = mkdtemp(prefix=root + '_', suffix='_astrometry.net')
            tmp_dir = True
        else:
            tmp_dir = False
        solved_file = os.path.join(output_dir, root + '.solved')

        args = [self._command, filename, '--dir', output_dir]

        for i, v in params.items():
            ndashes = 1 if len(i) == 1 else 2
            args.append("{0}{1}".format(ndashes * '-', i))
            if v is not None:
                args.append(str(v))

        try:
            logger.info('runing: ' + str(args))
            if stdout is None:
                stdout = subprocess.PIPE
            if stderr is None:
                stderr = subprocess.PIPE
            subprocess.check_call(args, stdout=stdout, stderr=stderr)

            # .solved file must exist and contain a binary one
            with open(solved_file, 'rb') as fd:
                if ord(fd.read()) != 1:
                    raise AstrometryNetUnsolvedField(filename)
            solved_wcs_file = os.path.join(output_dir, root + '.wcs')
            logger.info('Loading solved header from %s' % solved_wcs_file)
            solved_header = fits.getheader(solved_wcs_file, 0)

            # remove the tree if the file is temporary and not set to keep
            if not self._keep and tmp_dir:
                shutil.rmtree(output_dir)

            return solved_header

        except subprocess.CalledProcessError as e:
            if not self._keep and tmp_dir:
                shutil.rmtree(output_dir)
            raise e
        # If .solved file doesn't exist or contain one
        except (IOError, AstrometryNetUnsolvedField):
            if not self._keep and tmp_dir:
                shutil.rmtree(output_dir)
            raise AstrometryNetUnsolvedField(filename)


def create_xyls(fname, x, y, flux, imagew, imageh, header=None, dtype='f8'):
    '''
    Create and save the xyls file to run in astrometry.net

    Parameters:
    -----------
    fname : str
        The path to save the .xyls file.
    x : array_like
        X coordinates of the sources.
    y : array_like
        Y coordinates of the sources.
    flux : array_like
        Estimated flux of the sources.
    imagew : float or int
        Width of the original image. `IMAGEW` header field of .xyls
    imageh : float or int
        Height of the original image. `IMAGEH` header field of .xyls
    header : dict_like, optional
        Header of the orginal image. If None, no header will be added to the
        PrimaryHDU of the .xyls
    dtype : `numpy.dtype`, optional
        Data type of the fields. Default: 'f8'
    '''
    head = {'IMAGEW': imagew,
            'IMAGEH': imageh}
    sort = np.argsort(flux)
    xyls = np.array(list(zip(x, y, flux)),
                    np.dtype([('x', dtype), ('y', dtype), ('flux', dtype)]))
    f = fits.HDUList([fits.PrimaryHDU(header=header),
                      fits.BinTableHDU(xyls[sort[::-1]],
                                       header=fits.Header(head))])
    logger.debug('Saving .xyls to ' + fname)
    f.writeto(fname)


def solve_astrometry_xy(x, y, flux, image_header, image_width, image_height,
                        return_wcs=False, image_params={}):
    '''
    image_params are:
        pltscl: plate scale (arcsec/px)
        ra: right ascension (decimal degrees)
        dec: declination (decimal degrees)
        pltscl_key: header key for plate scale
        ra_key: header key for right ascension
        dec_key: header key for declination
        radius: maximum search radius
    '''
    f = NamedTemporaryFile(suffix='.xyls')
    create_xyls(f.name, x, y, flux, image_width, image_height,
                header=image_header)
    solved_header = AstrometrySolver().solve_field(f.name, wcs=return_wcs,
                                                   image_params=image_params)
    return solved_header


def solve_astrometry_image(filename, return_wcs=False, image_params={}):
    """
    image_params are:
        pltscl: plate scale (arcsec/px)
        ra: right ascension (decimal degrees)
        dec: declination (decimal degrees)
        pltscl_key: header key for plate scale
        ra_key: header key for right ascension
        dec_key: header key for declination
        radius: maximum search radius
    """
    return AstrometrySolver().solve_field(filename, wcs=return_wcs,
                                          image_params=image_params)


def fit_wcs(x, y, ra, dec, image_width, image_height, sip=False,
            command=shutil.which('fit-wcs')):
    """Run astrometry.net fit-wcs command

    sip is sip order, int
    """
    solved_wcs_file = NamedTemporaryFile(prefix='fitwcs', suffix='.wcs')
    tmp_table = NamedTemporaryFile(prefix='fitwcs_xyrd', suffix='.fits')

    xyrd = np.array(list(zip(x, y, ra, dec)),
                    np.dtype([('FIELD_X', 'f8'), ('FIELD_Y', 'f8'),
                              ('INDEX_RA', 'f8'), ('INDEX_DEC', 'f8')]))
    f = fits.HDUList([fits.PrimaryHDU(),
                      fits.BinTableHDU(xyrd)])
    logger.debug('Saving xyrd to ' + tmp_table.name)
    f.writeto(tmp_table.name)

    args = [command]
    args += ['-c', tmp_table.name]
    if sip:
        args += ['-s', str(sip), '-W', str(image_width), '-H',
                 str(image_height)]
    args += ['-o', solved_wcs_file.name]

    try:
        subprocess.check_call(args)
        logger.info('Loading solved header from {}'
                    .format(solved_wcs_file.name))
        solved_header = fits.getheader(solved_wcs_file.name, 0)
    except Exception as e:
        raise AstrometryNetUnsolvedField("Could not fit wcs to this lists."
                                         " Error: {}".format(e))

    return WCS(solved_header, relax=True)