.. include:: references.txt

Physical Quantities and Uncertanties
====================================

Any physical measurement is not a simple number. It is a number, but have a physical unit and an uncertainty related to it.

|astropy| has a very useful module called `~astropy.units`, that handles physical units and |Quantity|, a container intended to store physical measurements with units.. But it doesn't perform any error propagation.

To handle this and make the things a lot easier in ASTROPOP, we created a new class, called |QFloat| to handle both uncertainties and physical units at once. By |QFloat| we mean "Quantity Float", relating it to physical measurements. This class mainly wraps `~astropy.units` methods to handle units and perform error propagation in a coherent way. This module is used in a lot of places inside ASTROPOP, mainly in `~astropop.image_processing` and |Framedata| to ensure correct processing in terms of units and errors propagation.

.. WARNING:: In the actual state, |QFloat| assumes all uncertainties are standard deviation errors, performing the standard error propagation method. The error propagation also assumes that the uncertainties are uncorelated. This is fine for our usage, but may present problems if used out of this context.

The |QFloat| Class
------------------

The |QFloat| class stores basically 3 variables: the nominal value, the uncertainty and the physical unit. To create this class, just pass these values in the class constructor and you can access it using the proper properties.

    >>> from astropop.math import QFloat
    >>> import numpy as np
    >>> # A physical measure of 1.000+/-0.001 meters
    >>> qf = QFloat(1.0, 0.001, 'm')
    >>> print(qf.nominal) # the nominal value, must be 1.0
    1.0
    >>> print(qf.uncertainty) # the uncertainty, 0.001
    0.001
    >>> print(qf.unit) # astropy's physical unit, meter
    m
    >>> print(qf) # full representation.
    <QFloat 1.000+-0.001 m>

Note that, for the full representation of the quantity, the nominal and the uncertainty values are rounded to the first non-zero error decimal. Internally, the number is stored with all the computed decimal places and this rounding just appears in the string representation.

    >>> qf = QFloat(1.0583225, 0.0031495756, 'cm')
    >>> print(qf.nominal)
    1.0583225
    >>> print(qf.uncertainty)
    0.0031495756
    >>> print(qf)
    <QFloat 1.058+-0.003 cm>

|QFloat| also can store arrays of data, using the exactly same behavior.

    >>> qf = QFloat([1.0, 2.0, 3.0], [0.1, 0.2, 0.3], 'm/s')
    >>> print(qf)
    <QFloat
    array([1.0+-0.1, 2.0+-0.2, 3.0+-0.3], dtype=object)
    unit=m / s>

During the creation, you can omit `uncertainty` or `unit` arguments, but not the nominal value. We decided to don't make possible create empty |QFloat| instances. Omiting arguments, the code interprets it as:

- `unit`: setting `None` unit, or omiting it, the class automatically interpret it as `~astropy.units.dimensionless_unscaled`. This means: a number without physical unit.

    >>> qf_nounit = QFloat(1.0, 0.1)
    >>> print(qf_nounit)
    <QFloat 1.0+-0.1 >

- `uncertainty`: setting uncertainties as `None`, or omiting it, the code consider automatically the uncertainty as 0.0.

    >>> qf_nostd = QFloat(1.0, unit='m')
    >>> print(qf_nostd)
    <QFloat 1.0+-0.0 m>

You also can omit both, like converting a single dimensionless number to QFloat.

    >>> qf = QFloat(1.0)
    >>> print(qf)
    <QFloat 1.0+-0.0 >

Units and Conversion
--------------------

Physical units are fully handled with `~astropy.units` module. But we don't use |Quantity| class to store the files. Instead, the code perform itself the units checking and conversions. This is needed to make it compatible with uncertainties, but reduces the compatibility with |astropy| functions directly.

Internal conversion of units for math operations are made automatically and don't need manual intervention. But manual conversions are also possible using the ``<<`` operator or `~astropop.math.physical.QFloat.to` function. The same do the same thing: convert the actual |QFloat| to a new one, with the ne unit. Both accept `~astropy.units.UnitBase` instance or string for conversion.

    >>> from astropop.math import QFloat
    >>> from astropy import units
    >>> # One kilometer with 1 cm uncertainty
    >>> qf = QFloat(1000, 0.01, 'm')
    >>> qf << 'km'
    <QFloat 1.00000+-0.00001 km>
    >>> qf << units.cm
    <QFloat 100000+-1 cm>

If improper conversion (incompatible units), an `~astropy.units.UnitConversionError` is raised.

Math Operations and Error Propagation
-------------------------------------

As the main porpouse of this module, mathematical operations using physical quantities are performed between |QFloat| and compatible classes. We ensure a basic set of math operations to work, specially all the basic and trigonometric operations needed for basic data reduction. The code also support some basic |numpy| array functions, but not all of them.

The operations are performed with proper unit management and conversion (when necessary), and simplyfied uncorrelated error propagation. For a function :math:`f` of :math:`x, y, z, \cdots` variables, the error :math:`\sigma` associated to each one of them, is propagated using the common equation:

.. math::
    \sigma_f = \sqrt{ \left(\frac{\partial f}{\partial x}\right)^2 \sigma_x^2 + \left(\frac{\partial f}{\partial y} \right)^2 \sigma_y^2 + \left(\frac{\partial f}{\partial z} \right)^2 \sigma_z^2 + \cdots}

Note that, for this simplyfied version of the error propagation equation, all variables are assumed to be independent and errors uncorrelated. All the error propagation is done by |uncertainties|, that supports some error correlations. However, due to the way we have to handle the operations wrapping with units, it's expected that these correlated errors don't work well in our code.

Supported Math Operations
^^^^^^^^^^^^^^^^^^^^^^^^^

Since the math operations are the main reason of the |QFloat| to exist, they have a special focus in the implementation. All builtin Python math operations, with the exception of matrix multiplication, is implemented for |QFloat|. This makes possible to perform direct math operations with |QFloat|.

As example, to sum two |QFloat|, you just need to use the ``+`` operator.

    >>> qf1 = QFloat(1.0, 0.1, 'm')
    >>> qf2 = QFloat(2.0, 0.1, 'm')
    >>> qf1 + qf2
    <QFloat 3.0+-0.1 m>

ASTROPOP handles all the needed units checking and conversions and the result is dimensionality correct. For example:

    >>> qf1 = QFloat(60, 0.5, 'km')
    >>> qf2 = QFloat(7000, 700, 'm')
    >>> qf1 + qf2
    <QFloat 67.0+-0.9 km>
    >>> t = QFloat(2.0, 0.1, 'h')
    >>> qf1/t
    <QFloat 30+-2 km / h>

Incorrect dimensionality in operations will raise |UnitsError|.

    >>> qf1 = QFloat(3.0, 0.01, 'kg')
    >>> qf2 = QFloat(5.0, 0.2, 'K')
    >>> qf1 + qf2   # doctest: +SKIP
    UnitConversionError:

Supported Numpy Array Operations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some `Numpy array functions <https://numpy.org/doc/1.19/reference/routines.array-manipulation.html>`_ are supported built-in by the |QFloat|, but not all of them. These functions are intended to perform array manipulations, like append, reshape, transpose, etc. With this compatibility you can use the Numpy functions directly with |QFloat| objects, like:

    >>> qf = QFloat(np.zeros((100, 100)), np.zeros((100, 100)))
    >>> np.shape(qf)
    (100, 100)

One big difference from our compatibility to default Numpy is that for some functions, Numpy return the view of the array, for bigger performance. Our method, however, just return copies of the |QFloat|s with applied functions. The impact im performance is not so big and the memory usage will not be a problem, unless you use a very very large array.

The current Numpy array functions supported for this class are:

- `~numpy.append`
- `~numpy.around`
- `~numpy.clip`
- `~numpy.delete`
- `~numpy.expand_dims`
- `~numpy.flip`
- `~numpy.fliplr`
- `~numpy.flipud`
- `~numpy.insert`
- `~numpy.moveaxis`
- `~numpy.ravel`
- `~numpy.repeat`
- `~numpy.reshape`
- `~numpy.resize`
- `~numpy.roll`
- `~numpy.rollaxis`
- `~numpy.round`
- `~numpy.rot90`
- `~numpy.shape`
- `~numpy.size`
- `~numpy.squeeze`
- `~numpy.swapaxes`
- `~numpy.take`
- `~numpy.tile`
- `~numpy.transpose`

Supported Numpy Universal Functions (UFuncs)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To simplify the way we perform some math operations, we also support some important `Numpy Universal Functions <https://numpy.org/doc/stable/reference/ufuncs.html>`_, also named `~numpy.ufunc`. However, we had to simplify the implementation to get it running properly. So, the traditional ``kwargs`` passed to the `~numpy.ufunc`, like ``out``, ``where`` and others are ignored in our implementation.

The current supported ufuncs are:

- `~numpy.absolute` (`~numpy.abs`)
- `~numpy.add`
- `~numpy.arccos`
- `~numpy.arccosh`
- `~numpy.arcsin`
- `~numpy.arcsinh`
- `~numpy.arctan`
- `~numpy.arctanh`
- `~numpy.cos`
- `~numpy.cosh`
- `~numpy.deg2rad`
- `~numpy.degrees`
- `~numpy.divide` (`~numpy.true_divide`)
- `~numpy.exp`
- `~numpy.exp2`
- `~numpy.expm1`
- `~numpy.floor_divide`
- `~numpy.hypot`
- `~numpy.log`
- `~numpy.log10`
- `~numpy.log1p`
- `~numpy.log2`
- `~numpy.negative`
- `~numpy.positive`
- `~numpy.power` (`~numpy.float_power`)
- `~numpy.rad2deg`
- `~numpy.radians`
- `~numpy.remainder` (`~numpy.mod`)
- `~numpy.sin`
- `~numpy.sinh`
- `~numpy.square`
- `~numpy.sqrt`
- `~numpy.subtract`
- `~numpy.tan`
- `~numpy.tanh`

All the units checking is automatically performed by ASTROPOP. In fact, most of these functions just wrap standart operations of |QFloat|, since this class perform the operations in a way very similar to the `~numpy.ufunc`.

Trigonometric Math
^^^^^^^^^^^^^^^^^^

For trigonometric functions, like sines, cosines and tangents, the code is able to check the dimensionality of the numbers before perform the operation. So, only dimensionless numbers are accepted, being `~astropy.units.dimensionless_unscaled` or `~astropy.units.dimensionless_angles`. Any number with pyshical dimension don't make any sense inside trigonometric operations, which will raise an |UnitsError|.

To avoid an additional module containing trigonometric functions inside ASTROPOP, these operations are performed using the `~numpy.ufunc`s described earlier. The main difference here is the unit checking performed by ASTROPOP.

    >>> qf = QFloat(30, 0.1, 'deg')
    >>> np.cos(qf)
    <QFloat 0.8660+-0.0009 >
    >>> np.sin(qf)
    <QFloat 0.500+-0.002 >

For trionometric (and hyperbolic) functions, like `~numpy.sin` and `~numpy.sinh`, only angle are accepted. So, only |QFloat| with `~astropy.units.degree` or `~astropy.units.radians` will not raise |UnitsError|. Also, all these functions will result in `~astropy.units.dimensionless_unscaled` values.

For inverse trigonometric functions, like `~numpy.arcsin`, the inverse happens. The input must be a `~astropy.units.dimensionless_unscaled` |QFloat|, and output will be in units of `~astropy.units.radians`.

    >>> qf = QFloat(0.5, 0.01)
    >>> np.arcsin(qf)
    <QFloat 0.52+-0.01 rad>

Comparisons Notes
-----------------

Comparing two numbers with units and uncertainties is an ambiguous thing. There are multiple ways to consider two numbers equal or different, or even greater or smaller. Due to this, we had to assume some conventions in the processing.

Equality
^^^^^^^^

We consider two numbers equal if they have the same nominal and standard deviation values in the same unit. This means, they are exactly equal in everything, meaning a more programing-like approach. Like:

    >>> # 1.0+/-0.1 meters
    >>> qf1 = QFloat(1.0, 0.1, 'm')
    >>> # same as above, but in cm
    >>> qf2 = QFloat(100, 10, 'cm')
    >>> print(qf1 == qf2)
    True

So, the simple fact that two numers have different error bars imply that they are different.

    >>> # 1.0+/-0.2 meters. Same number, with different error
    >>> qf3 = QFloat(1.0, 0.2, 'm')
    >>> print(qf1 == qf3)
    False
    >>> # 0.5+/-0.1 meters
    >>> qf4 = QFloat(0.5, 0.1, 'm')
    >>> print(qf1 == qf4)
    False

Of course, the different operator works in the exactly same way.

    >>> print(qf1 != qf2)
    False
    >>> print(qf1 != qf3)
    True
    >>> print(qf1 != qf4)
    True

When comparing numbers with same dimension units, the code automatically converts if to compare. But, if incompatible units (different dimensions) are compared, they automatically are considered different. In physical terms, 1 second is different from 1 meter.

    >>> # Same nominal values of qf1, but in seconds
    >>> qf5 = (1.0, 0.1, 's')
    >>> print(qf1 == qf5)
    False
    >>> print(qf1 != qf5)
    True

Equality considering errors
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To check physical equality, which consider if the numbers are equal inside the error bars, we created the `~astropop.math.physical.equal_within_errors` method. In this method we assume two numbers (:math:`a` and :math:`b`) are equal if their different is smaller than the sum of the errors (:math:`\sigma_a` and :math:`\sigma_b`).

.. math::
    | a - b | <= \sigma_a + \sigma_b

In other words, these two numbers are equal if they intercept each other, considering error bars. Or, within the errors, they have ate least one value in common.

So, for a proper physical check of equalities, use `~astropop.math.physical.equal_within_errors` instead of ``==`` operator. For example:

    >>> from astropop.math.physical import QFloat, equal_within_errors
    >>> qf1 = QFloat(1.1, 0.1, 'm')
    >>> qf2 = QFloat(1.15, 0.05, 'm')
    >>> print(equal_within_errors(qf1, qf2))
    True

Inequalities
^^^^^^^^^^^^

Inequality handling is more ambiguous then equality to define. To avoid a complex API and keep the things in a coherent way, we perform greater, greater or equal, smaller and smaller or equal operations just comparing the nominal values of the numbers. For example:

    >>> qf1 = QFloat(1.1, 0.1, 'm')
    >>> qf2 = QFloat(1.15, 0.05, 'm')
    >>> print(qf1 < qf2)
    True
    >>> print(qf2 >= qf1)
    True
    >>> print(qf2 < qf1)
    False

Note that errors are note being considered in operations. However, this operation perfmors full handling of physical units. So:

    >>> qf1 = QFloat(1.0, 0.1, 'm')
    >>> qf2 = QFloat(50, 10, 'cm')
    >>> print(qf1 >= qf2)
    True

These comparisons can only be performed by same dimension measurements. If incompatible units are used, |UnitsError| is raised.

Physical Quantities API
-----------------------

.. autoclass:: astropop.math.physical.QFloat
    :members:
    :undoc-members:
    :show-inheritance:
    :inherited-members:
.. autofunction:: astropop.math.physical.equal_within_errors
.. autofunction:: astropop.math.physical.qfloat
.. autofunction:: astropop.math.physical.same_unit
