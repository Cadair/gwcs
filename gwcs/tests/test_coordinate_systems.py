# Licensed under a 3-clause BSD style license - see LICENSE.rst
from functools import partial

import pytest
import numpy as np
from numpy.testing import assert_allclose

import astropy.units as u
from astropy.time import Time
from astropy import coordinates as coord
from astropy.time import Time
from astropy.tests.helper import assert_quantity_allclose

from .. import coordinate_frames as cf


coord_frames = coord.builtin_frames.__all__[:]

# Need to write a better test, using a dict {coord_frame: input_parameters}
# For now remove OffsetFrame, issue #55
try:
    coord_frames.remove("SkyOffsetFrame")
except ValueError as ve:
    pass


icrs = cf.CelestialFrame(reference_frame=coord.ICRS(), axes_order=(0, 1))
detector = cf.Frame2D(name='detector', axes_order=(0, 1))
focal = cf.Frame2D(name='focal', axes_order=(0, 1), unit=(u.m, u.m))

spec1 = cf.SpectralFrame(name='freq', unit=[u.Hz, ], axes_order=(2, ))
spec2 = cf.SpectralFrame(name='wave', unit=[u.m, ], axes_order=(2, ), axes_names=('lambda', ))

comp1 = cf.CompositeFrame([icrs, spec1])
comp2 = cf.CompositeFrame([focal, spec2])
comp = cf.CompositeFrame([comp1, cf.SpectralFrame(axes_order=(3,), unit=(u.m,))])

xscalar = 1
yscalar = 2
xarr = np.arange(5)
yarr = np.arange(5)

inputs2 = [(xscalar, yscalar), (xarr, yarr)]
inputs1 = [xscalar, xarr]
inputs3 = [(xscalar, yscalar, xscalar), (xarr, yarr, xarr)]


def test_units():
    assert(comp1.unit == (u.deg, u.deg, u.Hz))
    assert(comp2.unit == (u.m, u.m, u.m))
    assert(comp.unit == (u.deg, u.deg, u.Hz, u.m))


@pytest.mark.parametrize('inputs', inputs2)
def test_coordinates_spatial(inputs):
    sky_coo = icrs.coordinates(*inputs)
    assert isinstance(sky_coo, coord.SkyCoord)
    assert_allclose((sky_coo.ra.value, sky_coo.dec.value), inputs)
    focal_coo = focal.coordinates(*inputs)
    assert_allclose([coo.value for coo in focal_coo], inputs)
    assert [coo.unit for coo in focal_coo] == [u.m, u.m]


@pytest.mark.parametrize('inputs', inputs1)
def test_coordinates_spectral(inputs):
    wave = spec2.coordinates(inputs)
    assert_allclose(wave.value, inputs)
    assert wave.unit == 'meter'
    assert isinstance(wave, u.Quantity)


@pytest.mark.parametrize('inputs', inputs3)
def test_coordinates_composite(inputs):
    frame = cf.CompositeFrame([icrs, spec2])
    result = frame.coordinates(*inputs)
    assert isinstance(result[0], coord.SkyCoord)
    assert_allclose((result[0].ra.value, result[0].dec.value), inputs[:2])
    assert_allclose(result[1].value, inputs[2])


@pytest.mark.parametrize(('frame'), coord_frames)
def test_celestial_attributes_length(frame):
    """
    Test getting default values for  CoordinateFrame attributes from reference_frame.
    """
    cel = cf.CelestialFrame(reference_frame=getattr(coord, frame)())
    assert(len(cel.axes_names) == len(cel.axes_type) == len(cel.unit) ==
           len(cel.axes_order) == cel.naxes)


def test_axes_type():
    assert(icrs.axes_type == ('SPATIAL', 'SPATIAL'))
    assert(spec1.axes_type == ('SPECTRAL',))
    assert(detector.axes_type == ('SPATIAL', 'SPATIAL'))
    assert(focal.axes_type == ('SPATIAL', 'SPATIAL'))


def test_temporal_relative():
    t = cf.TemporalFrame(reference_time=Time("2018-01-01T00:00:00"), unit=u.s)
    assert t.coordinates(10) == Time("2018-01-01T00:00:00") + 10 * u.s
    assert t.coordinates(10 * u.s) == Time("2018-01-01T00:00:00") + 10 * u.s

    a = t.coordinates((10, 20))
    assert a[0] == Time("2018-01-01T00:00:00") + 10 * u.s
    assert a[1] == Time("2018-01-01T00:00:00") + 20 * u.s

    t = cf.TemporalFrame(reference_time=Time("2018-01-01T00:00:00"))
    assert t.coordinates(10 * u.s) == Time("2018-01-01T00:00:00") + 10 * u.s

    a = t.coordinates((10, 20) * u.s)
    assert a[0] == Time("2018-01-01T00:00:00") + 10 * u.s
    assert a[1] == Time("2018-01-01T00:00:00") + 20 * u.s


def test_temporal_absolute():
    t = cf.TemporalFrame()
    assert t.coordinates("2018-01-01T00:00:00") == Time("2018-01-01T00:00:00")

    a = t.coordinates(("2018-01-01T00:00:00", "2018-01-01T00:10:00"))
    assert a[0] == Time("2018-01-01T00:00:00")
    assert a[1] == Time("2018-01-01T00:10:00")

    t = cf.TemporalFrame(reference_frame=partial(Time, scale='tai'))
    assert t.coordinates("2018-01-01T00:00:00") == Time("2018-01-01T00:00:00", scale='tai')


@pytest.mark.parametrize('inp', [
    (10*u.deg, 20*u.deg),
    ((10*u.deg, 20*u.deg),),
    (u.Quantity([10, 20], u.deg),),
    (coord.SkyCoord(10*u.deg, 20*u.deg, frame=coord.ICRS),),
    # This is the same as 10,20 in ICRS
    (coord.SkyCoord(119.26936774, -42.79039286, unit=u.deg, frame='galactic'),)
    ])
def test_coordinate_to_quantity_celestial(inp):
    cel = cf.CelestialFrame(reference_frame=coord.ICRS(), axes_order=(0, 1))

    lon, lat = cel.coordinate_to_quantity(*inp)
    assert_quantity_allclose(lon, 10*u.deg)
    assert_quantity_allclose(lat, 20*u.deg)


@pytest.mark.parametrize('inp', [
    (100,),
    (100*u.nm,),
    (0.1*u.um,),
    ])
def test_coordinate_to_quantity_spectral(inp):
    spec = cf.SpectralFrame(unit=u.nm, axes_order=(1, ))
    wav = spec.coordinate_to_quantity(*inp)
    assert_quantity_allclose(wav, 100*u.nm)


@pytest.mark.parametrize('inp', [
    (Time("2011-01-01T00:00:10"),),
    (10*u.s,)
    ])
def test_coordinate_to_quantity_temporal(inp):
    temp = cf.TemporalFrame(reference_time=Time("2011-01-01T00:00:00"), unit=u.s)

    t = temp.coordinate_to_quantity(*inp)

    assert_quantity_allclose(t, 10*u.s)

    temp2 = cf.TemporalFrame(unit=u.s)

    tt = Time("2011-01-01T00:00:00")
    t = temp2.coordinate_to_quantity(tt)

    assert t is tt


@pytest.mark.parametrize('inp', [
    (211*u.AA, 0*u.s, 0*u.arcsec, 0*u.arcsec),
    (211*u.AA, 0*u.s, (0*u.arcsec, 0*u.arcsec)),
    (211*u.AA, 0*u.s, (0, 0)*u.arcsec),
    (211*u.AA, Time("2011-01-01T00:00:00"), (0, 0)*u.arcsec),
    (211*u.AA, Time("2011-01-01T00:00:00"), coord.SkyCoord(0, 0, unit=u.arcsec)),
    ])
def test_coordinate_to_quantity_composite(inp):
    # Composite
    wave_frame = cf.SpectralFrame(axes_order=(0, ), unit=u.AA)
    time_frame = cf.TemporalFrame(
        axes_order=(1, ), unit=u.s, reference_time=Time("2011-01-01T00:00:00"))
    sky_frame = cf.CelestialFrame(axes_order=(2, 3), reference_frame=coord.ICRS())

    comp = cf.CompositeFrame([wave_frame, time_frame, sky_frame])

    coords = comp.coordinate_to_quantity(*inp)

    expected = (211*u.AA, 0*u.s, 0*u.arcsec, 0*u.arcsec)
    for output, exp in zip(coords, expected):
        assert_quantity_allclose(output, exp)
