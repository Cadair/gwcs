# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
Tests the API defined in astropy APE 14 (https://doi.org/10.5281/zenodo.1188875).
"""

import astropy.modeling.models as m
import astropy.units as u
import numpy as np
import pytest
from astropy import coordinates as coord
from astropy import time
from astropy.wcs.wcsapi import HighLevelWCSWrapper
from numpy.testing import assert_allclose, assert_array_equal

import gwcs
import gwcs.coordinate_frames as cf


# Shorthand the name of the 2d gwcs fixture
@pytest.fixture
def wcsobj(request):
    return request.getfixturevalue(request.param)


wcs_objs = pytest.mark.parametrize("wcsobj", ["gwcs_2d_spatial_shift"], indirect=True)


@pytest.fixture
def wcs_ndim_types_units(request):
    """
    Generate a wcs and the expected ndim, types, and units.
    """
    ndim = {
        "gwcs_2d_spatial_shift": (2, 2),
        "gwcs_2d_spatial_reordered": (2, 2),
        "gwcs_1d_freq": (1, 1),
        "gwcs_3d_spatial_wave": (3, 3),
        "gwcs_4d_identity_units": (4, 4),
    }
    types = {
        "gwcs_2d_spatial_shift": ("pos.eq.ra", "pos.eq.dec"),
        "gwcs_2d_spatial_reordered": ("pos.eq.dec", "pos.eq.ra"),
        "gwcs_1d_freq": ("em.freq",),
        "gwcs_3d_spatial_wave": ("pos.eq.ra", "pos.eq.dec", "em.wl"),
        "gwcs_4d_identity_units": ("pos.eq.ra", "pos.eq.dec", "em.wl", "time"),
    }
    units = {
        "gwcs_2d_spatial_shift": ("deg", "deg"),
        "gwcs_2d_spatial_reordered": ("deg", "deg"),
        "gwcs_1d_freq": ("Hz",),
        "gwcs_3d_spatial_wave": ("deg", "deg", "m"),
        "gwcs_4d_identity_units": ("deg", "deg", "nm", "s"),
    }

    return (
        request.getfixturevalue(request.param),
        ndim[request.param],
        types[request.param],
        units[request.param],
    )


# # x, y inputs - scalar and array
x, y = 1, 2
xarr, yarr = np.ones((3, 4)), np.ones((3, 4)) + 1

fixture_names = [
    "gwcs_2d_spatial_shift",
    "gwcs_2d_spatial_reordered",
    "gwcs_1d_freq",
    "gwcs_3d_spatial_wave",
    "gwcs_4d_identity_units",
]
fixture_wcs_ndim_types_units = pytest.mark.parametrize(
    "wcs_ndim_types_units", fixture_names, indirect=True
)
all_wcses_names = [
    *fixture_names,
    "gwcs_3d_identity_units",
    "gwcs_stokes_lookup",
    "gwcs_3d_galactic_spectral",
]
fixture_all_wcses = pytest.mark.parametrize("wcsobj", all_wcses_names, indirect=True)


@fixture_all_wcses
def test_lowlevel_types(wcsobj):
    try:
        # Skip this on older versions of astropy where it doesn't exist.
        from astropy.wcs.wcsapi.tests.utils import validate_low_level_wcs_types
    except ImportError:
        return

    validate_low_level_wcs_types(wcsobj)


@fixture_all_wcses
def test_names(wcsobj):
    assert wcsobj.world_axis_names == wcsobj.output_frame.axes_names
    assert wcsobj.pixel_axis_names == wcsobj.input_frame.axes_names


def test_names_split(gwcs_3d_galactic_spectral):
    wcs = gwcs_3d_galactic_spectral
    assert (
        wcs.world_axis_names
        == wcs.output_frame.axes_names
        == ("Latitude", "Frequency", "Longitude")
    )


@fixture_wcs_ndim_types_units
def test_pixel_n_dim(wcs_ndim_types_units):
    wcsobj, ndims, *_ = wcs_ndim_types_units
    assert wcsobj.pixel_n_dim == ndims[0]


@fixture_wcs_ndim_types_units
def test_world_n_dim(wcs_ndim_types_units):
    wcsobj, ndims, *_ = wcs_ndim_types_units
    assert wcsobj.world_n_dim == ndims[1]


@fixture_wcs_ndim_types_units
def test_world_axis_physical_types(wcs_ndim_types_units):
    wcsobj, ndims, physical_types, world_units = wcs_ndim_types_units
    assert wcsobj.world_axis_physical_types == physical_types


@fixture_wcs_ndim_types_units
def test_world_axis_units(wcs_ndim_types_units):
    wcsobj, ndims, physical_types, world_units = wcs_ndim_types_units
    assert wcsobj.world_axis_units == world_units


@pytest.mark.parametrize(("x", "y"), zip((x, xarr), (y, yarr), strict=False))
def test_pixel_to_world_values(gwcs_2d_spatial_shift, x, y):
    wcsobj = gwcs_2d_spatial_shift
    assert_allclose(wcsobj.pixel_to_world_values(x, y), wcsobj(x, y))


@pytest.mark.parametrize(("x", "y"), zip((x, xarr), (y, yarr), strict=False))
def test_pixel_to_world_values_units_2d(gwcs_2d_shift_scale_quantity, x, y):
    wcsobj = gwcs_2d_shift_scale_quantity

    call_pixel = x * u.pix, y * u.pix
    api_pixel = x, y

    call_world = wcsobj(*call_pixel)
    api_world = wcsobj.pixel_to_world_values(*api_pixel)

    # Check that call returns quantities and api doesn't
    assert all(isinstance(a, u.Quantity) for a in call_world)
    assert all(not isinstance(a, u.Quantity) for a in api_world)

    # Check that they are the same (and implicitly in the same units)
    assert_allclose(u.Quantity(call_world).value, api_world)

    new_call_pixel = wcsobj.invert(*call_world)
    [assert_allclose(n, p) for n, p in zip(new_call_pixel, call_pixel, strict=False)]

    new_api_pixel = wcsobj.world_to_pixel_values(*api_world)
    [assert_allclose(n, p) for n, p in zip(new_api_pixel, api_pixel, strict=False)]


@pytest.mark.parametrize(("x"), [x, xarr])
def test_pixel_to_world_values_units_1d(gwcs_1d_freq_quantity, x):
    wcsobj = gwcs_1d_freq_quantity

    call_pixel = x * u.pix
    api_pixel = x

    call_world = wcsobj(call_pixel)
    api_world = wcsobj.pixel_to_world_values(api_pixel)

    # Check that call returns quantities and api doesn't
    assert isinstance(call_world, u.Quantity)
    assert not isinstance(api_world, u.Quantity)

    # Check that they are the same (and implicitly in the same units)
    assert_allclose(u.Quantity(call_world).value, api_world)

    new_call_pixel = wcsobj.invert(call_world)
    assert_allclose(new_call_pixel, call_pixel)

    new_api_pixel = wcsobj.world_to_pixel_values(api_world)
    assert_allclose(new_api_pixel, api_pixel)


@pytest.mark.parametrize(("x", "y"), zip((x, xarr), (y, yarr), strict=False))
def test_array_index_to_world_values(gwcs_2d_spatial_shift, x, y):
    wcsobj = gwcs_2d_spatial_shift
    assert_allclose(wcsobj.array_index_to_world_values(x, y), wcsobj(y, x))


def test_world_axis_object_components_2d(gwcs_2d_spatial_shift):
    waoc = gwcs_2d_spatial_shift.world_axis_object_components
    assert waoc[0][:2] == ("celestial", 0)
    assert callable(waoc[0][2])
    assert waoc[1][:2] == ("celestial", 1)
    assert callable(waoc[1][2])


def test_world_axis_object_components_2d_generic(gwcs_2d_quantity_shift):
    waoc = gwcs_2d_quantity_shift.world_axis_object_components
    assert waoc == [("SPATIAL", 0, "value"), ("SPATIAL1", 0, "value")]


def test_world_axis_object_components_1d(gwcs_1d_freq):
    waoc = gwcs_1d_freq.world_axis_object_components
    assert [c[:2] for c in waoc] == [("spectral", 0)]
    assert callable(waoc[0][2])


def test_world_axis_object_components_4d(gwcs_4d_identity_units):
    waoc = gwcs_4d_identity_units.world_axis_object_components
    first_two = [c[:2] for c in waoc]
    last_one = [c[2] for c in waoc]
    assert first_two == [
        ("celestial", 0),
        ("celestial", 1),
        ("spectral", 0),
        ("temporal", 0),
    ]
    assert all(callable(last) for last in last_one)


def test_world_axis_object_classes_2d(gwcs_2d_spatial_shift):
    waoc = gwcs_2d_spatial_shift.world_axis_object_classes
    assert waoc["celestial"][0] is coord.SkyCoord
    assert waoc["celestial"][1] == ()
    assert "frame" in waoc["celestial"][2]
    assert "unit" in waoc["celestial"][2]
    assert isinstance(waoc["celestial"][2]["frame"], coord.ICRS)
    assert tuple(waoc["celestial"][2]["unit"]) == (u.deg, u.deg)


def test_world_axis_object_classes_2d_generic(gwcs_2d_quantity_shift):
    waoc = gwcs_2d_quantity_shift.world_axis_object_classes
    assert waoc["SPATIAL"][0] is u.Quantity
    assert waoc["SPATIAL1"][0] is u.Quantity
    assert waoc["SPATIAL"][1] == ()
    assert waoc["SPATIAL1"][1] == ()
    assert "unit" in waoc["SPATIAL"][2]
    assert "unit" in waoc["SPATIAL1"][2]
    assert waoc["SPATIAL"][2]["unit"] == u.km
    assert waoc["SPATIAL1"][2]["unit"] == u.km


def test_world_axis_object_classes_4d(gwcs_4d_identity_units):
    waoc = gwcs_4d_identity_units.world_axis_object_classes
    assert waoc["celestial"][0] is coord.SkyCoord
    assert waoc["celestial"][1] == ()
    assert "frame" in waoc["celestial"][2]
    assert "unit" in waoc["celestial"][2]
    assert isinstance(waoc["celestial"][2]["frame"], coord.ICRS)
    assert tuple(waoc["celestial"][2]["unit"]) == (u.deg, u.deg)

    temporal = waoc["temporal"]
    assert temporal[0] is time.Time
    assert temporal[1] == ()
    assert temporal[2] == {
        "unit": u.s,
        "format": "isot",
        "scale": "utc",
        "precision": 3,
        "in_subfmt": "*",
        "out_subfmt": "*",
        "location": None,
    }


def _compare_frame_output(wc1, wc2):
    if isinstance(wc1, coord.SkyCoord):
        assert isinstance(wc1.frame, type(wc2.frame))
        assert u.allclose(wc1.spherical.lon, wc2.spherical.lon, equal_nan=True)
        assert u.allclose(wc1.spherical.lat, wc2.spherical.lat, equal_nan=True)
        assert u.allclose(
            wc1.spherical.distance, wc2.spherical.distance, equal_nan=True
        )

    elif isinstance(wc1, u.Quantity):
        assert u.allclose(wc1, wc2, equal_nan=True)

    elif isinstance(wc1, time.Time):
        assert u.allclose((wc1 - wc2).to(u.s), 0 * u.s)

    elif isinstance(wc1, str | coord.StokesCoord):
        assert wc1 == wc2

    else:
        msg = f"Can't Compare {type(wc1)}"
        raise TypeError(msg)


@fixture_all_wcses
def test_high_level_wrapper(wcsobj, request):
    hlvl = HighLevelWCSWrapper(wcsobj)

    pixel_input = [3] * wcsobj.pixel_n_dim
    if wcsobj.bounding_box is not None:
        for i, interval in wcsobj.bounding_box.intervals.items():
            bbox_min = u.Quantity(interval.lower).value
            pixel_input[i] = max(bbox_min + 1, pixel_input[i])

    # Assert that both APE 14 API and GWCS give the same answer The APE 14 API
    # uses the mixin class and __call__ calls values_to_high_level_objects
    wc1 = hlvl.pixel_to_world(*pixel_input)
    wc2 = wcsobj(*pixel_input, with_units=True)

    assert type(wc1) is type(wc2)

    if isinstance(wc1, list | tuple):
        for w1, w2 in zip(wc1, wc2, strict=False):
            _compare_frame_output(w1, w2)
    else:
        _compare_frame_output(wc1, wc2)

    # we have just asserted that wc1 and wc2 are equal
    if not isinstance(wc1, list | tuple):
        wc1 = (wc1,)

    pix_out1 = hlvl.world_to_pixel(*wc1)
    pix_out2 = wcsobj.invert(*wc1)

    if not isinstance(pix_out2, list | tuple):
        pix_out2 = (pix_out2,)

    if wcsobj.forward_transform.uses_quantity:
        pix_out2 = tuple(
            p.to_value(unit)
            for p, unit in zip(pix_out2, wcsobj.input_frame.unit, strict=False)
        )

    np.testing.assert_allclose(pix_out1, pixel_input)
    np.testing.assert_allclose(pix_out2, pixel_input)


def test_stokes_wrapper(gwcs_stokes_lookup):
    hlvl = HighLevelWCSWrapper(gwcs_stokes_lookup)

    pixel_input = [0, 1, 2, 3]

    out = hlvl.pixel_to_world(pixel_input * u.pix)

    assert list(out) == ["I", "Q", "U", "V"]

    pixel_input = [
        [0, 1, 2, 3],
        [0, 1, 2, 3],
        [0, 1, 2, 3],
        [0, 1, 2, 3],
    ]

    out = hlvl.pixel_to_world(pixel_input * u.pix)

    expected = coord.StokesCoord(
        [
            ["I", "Q", "U", "V"],
            ["I", "Q", "U", "V"],
            ["I", "Q", "U", "V"],
            ["I", "Q", "U", "V"],
        ]
    )

    assert (out == expected).all()

    pixel_input = [-1, 4]

    out = hlvl.pixel_to_world(pixel_input * u.pix)

    assert np.isnan(out.value).all()

    pixel_input = [[-1, 4], [1, 2]]

    out = hlvl.pixel_to_world(pixel_input * u.pix)

    assert np.isnan(out[0].value).all()
    assert (out[1] == ["Q", "U"]).all()

    out = hlvl.pixel_to_world(1 * u.pix)

    assert isinstance(out, coord.StokesCoord)
    assert out == "Q"


@wcs_objs
def test_array_shape(wcsobj):
    assert wcsobj.array_shape is None

    wcsobj.array_shape = (2040, 1020)
    assert_array_equal(wcsobj.array_shape, (2040, 1020))

    assert wcsobj.array_shape == wcsobj.pixel_shape[::-1]

    wcsobj.pixel_shape = (1111, 2222)
    assert wcsobj.array_shape == (2222, 1111)


@wcs_objs
def test_pixel_bounds(wcsobj):
    assert wcsobj.pixel_bounds is None

    wcsobj.bounding_box = ((-0.5, 2039.5), (-0.5, 1019.5))
    assert_array_equal(wcsobj.pixel_bounds, wcsobj.bounding_box)


@wcs_objs
def test_axis_correlation_matrix(wcsobj):
    assert_array_equal(wcsobj.axis_correlation_matrix, np.identity(2))


@wcs_objs
def test_serialized_classes(wcsobj):
    assert not wcsobj.serialized_classes


@wcs_objs
def test_low_level_wcs(wcsobj):
    assert id(wcsobj.low_level_wcs) == id(wcsobj)


@wcs_objs
def test_pixel_to_world(wcsobj):
    values = wcsobj(x, y)
    result = wcsobj.pixel_to_world(x, y)
    assert isinstance(result, coord.SkyCoord)
    assert_allclose(values[0] * u.deg, result.data.lon)
    assert_allclose(values[1] * u.deg, result.data.lat)


@wcs_objs
def test_array_index_to_world(wcsobj):
    values = wcsobj(x, y)
    result = wcsobj.array_index_to_world(y, x)
    assert isinstance(result, coord.SkyCoord)
    assert_allclose(values[0] * u.deg, result.data.lon)
    assert_allclose(values[1] * u.deg, result.data.lat)


def test_pixel_to_world_quantity(gwcs_2d_shift_scale, gwcs_2d_shift_scale_quantity):
    result1 = gwcs_2d_shift_scale.pixel_to_world(x, y)
    result2 = gwcs_2d_shift_scale_quantity.pixel_to_world(x, y)
    assert isinstance(result2, coord.SkyCoord)
    assert_allclose(result1.data.lon, result2.data.lon)
    assert_allclose(result1.data.lat, result2.data.lat)

    # test with Quantity pixel inputs
    result1 = gwcs_2d_shift_scale.pixel_to_world(x * u.pix, y * u.pix)
    result2 = gwcs_2d_shift_scale_quantity.pixel_to_world(x * u.pix, y * u.pix)
    assert isinstance(result2, coord.SkyCoord)
    assert_allclose(result1.data.lon, result2.data.lon)
    assert_allclose(result1.data.lat, result2.data.lat)

    # test for pixel units
    with pytest.raises(ValueError):  # noqa: PT011
        gwcs_2d_shift_scale.pixel_to_world(x * u.Jy, y * u.Jy)


def test_array_index_to_world_quantity(
    gwcs_2d_shift_scale, gwcs_2d_shift_scale_quantity
):
    result0 = gwcs_2d_shift_scale.pixel_to_world(x, y)
    result1 = gwcs_2d_shift_scale.array_index_to_world(y, x)
    result2 = gwcs_2d_shift_scale_quantity.array_index_to_world(y, x)
    assert isinstance(result2, coord.SkyCoord)
    assert_allclose(result1.data.lon, result2.data.lon)
    assert_allclose(result1.data.lat, result2.data.lat)
    assert_allclose(result0.data.lon, result1.data.lon)
    assert_allclose(result0.data.lat, result1.data.lat)

    # test with Quantity pixel inputs
    result0 = gwcs_2d_shift_scale.pixel_to_world(x * u.pix, y * u.pix)
    result1 = gwcs_2d_shift_scale.array_index_to_world(y * u.pix, x * u.pix)
    result2 = gwcs_2d_shift_scale_quantity.array_index_to_world(y * u.pix, x * u.pix)
    assert isinstance(result2, coord.SkyCoord)
    assert_allclose(result1.data.lon, result2.data.lon)
    assert_allclose(result1.data.lat, result2.data.lat)
    assert_allclose(result0.data.lon, result1.data.lon)
    assert_allclose(result0.data.lat, result1.data.lat)

    # test for pixel units
    with pytest.raises(ValueError):  # noqa: PT011
        gwcs_2d_shift_scale.array_index_to_world(x * u.Jy, y * u.Jy)


def test_world_to_pixel_quantity(gwcs_2d_shift_scale, gwcs_2d_shift_scale_quantity):
    skycoord = gwcs_2d_shift_scale.pixel_to_world(x, y)
    result1 = gwcs_2d_shift_scale.world_to_pixel(skycoord)
    result2 = gwcs_2d_shift_scale_quantity.world_to_pixel(skycoord)
    assert_allclose(result1, (x, y))
    assert_allclose(result2, (x, y))


def test_world_to_array_index_quantity(
    gwcs_2d_shift_scale, gwcs_2d_shift_scale_quantity
):
    skycoord = gwcs_2d_shift_scale.pixel_to_world(x, y)
    result0 = gwcs_2d_shift_scale.world_to_pixel(skycoord)
    result1 = gwcs_2d_shift_scale.world_to_array_index(skycoord)
    result2 = gwcs_2d_shift_scale_quantity.world_to_array_index(skycoord)
    assert_allclose(result0, (x, y))
    assert_allclose(result1, (y, x))
    assert_allclose(result2, (y, x))


@pytest.fixture(params=[0, 1])
def sky_ra_dec(request, gwcs_2d_spatial_shift):
    ref_frame = gwcs_2d_spatial_shift.output_frame.reference_frame
    ra, dec = 2, 4
    if request.param == 0:
        sky = coord.SkyCoord(ra * u.deg, dec * u.deg, frame=ref_frame)
    else:
        ra = np.ones((3, 4)) * ra
        dec = np.ones((3, 4)) * dec
        sky = coord.SkyCoord(ra * u.deg, dec * u.deg, frame=ref_frame)
    return sky, ra, dec


def test_world_to_pixel(gwcs_2d_spatial_shift, sky_ra_dec):
    wcsobj = gwcs_2d_spatial_shift
    sky, ra, dec = sky_ra_dec
    assert_allclose(wcsobj.world_to_pixel(sky), wcsobj.invert(ra, dec))


def test_world_to_array_index(gwcs_simple_imaging, sky_ra_dec):
    wcsobj = gwcs_simple_imaging
    sky, ra, dec = sky_ra_dec

    assert_allclose(
        wcsobj.world_to_array_index(sky),
        wcsobj.invert(ra * u.deg, dec * u.deg, with_units=False)[::-1],
    )


def test_world_to_pixel_values(gwcs_2d_spatial_shift, sky_ra_dec):
    wcsobj = gwcs_2d_spatial_shift
    sky, ra, dec = sky_ra_dec

    assert_allclose(wcsobj.world_to_pixel_values(ra, dec), wcsobj.invert(ra, dec))


def test_world_to_array_index_values(gwcs_simple_imaging, sky_ra_dec):
    wcsobj = gwcs_simple_imaging
    sky, ra, dec = sky_ra_dec

    assert_allclose(
        wcsobj.world_to_array_index_values(ra, dec),
        wcsobj.invert(ra * u.deg, dec * u.deg, with_units=False)[::-1],
    )


def test_ndim_str_frames(gwcs_with_frames_strings):
    wcsobj = gwcs_with_frames_strings
    assert wcsobj.pixel_n_dim == 4
    assert wcsobj.world_n_dim == 3


def test_composite_many_base_frame():
    q_frame_1 = cf.CoordinateFrame(
        name="distance", axes_order=(0,), naxes=1, axes_type="SPATIAL", unit=(u.m,)
    )
    q_frame_2 = cf.CoordinateFrame(
        name="distance", axes_order=(1,), naxes=1, axes_type="SPATIAL", unit=(u.m,)
    )
    frame = cf.CompositeFrame([q_frame_1, q_frame_2])

    wao_classes = frame.world_axis_object_classes

    assert len(wao_classes) == 2
    assert not set(wao_classes.keys()).difference({"SPATIAL", "SPATIAL1"})

    wao_components = frame.world_axis_object_components

    assert len(wao_components) == 2
    assert not {c[0] for c in wao_components}.difference({"SPATIAL", "SPATIAL1"})


def test_coordinate_frame_api():
    forward = m.Linear1D(slope=0.1 * u.deg / u.pix, intercept=0 * u.deg)

    output_frame = cf.CoordinateFrame(
        1, "SPATIAL", (0,), unit=(u.deg,), name="sepframe"
    )
    input_frame = cf.CoordinateFrame(1, "PIXEL", (0,), unit=(u.pix,))

    wcs = gwcs.WCS(
        forward_transform=forward, input_frame=input_frame, output_frame=output_frame
    )

    world = wcs.pixel_to_world(0)
    assert isinstance(world, u.Quantity)

    pixel = wcs.world_to_pixel(world)
    assert isinstance(pixel, float)

    pixel2 = wcs.invert(world)
    assert u.allclose(pixel2, 0 * u.pix)


def test_world_axis_object_components_units(gwcs_3d_identity_units):
    from astropy.wcs.wcsapi.high_level_api import high_level_objects_to_values

    wcs = gwcs_3d_identity_units
    world = wcs.pixel_to_world(1, 1, 1)

    values = high_level_objects_to_values(*world, low_level_wcs=wcs)

    expected_values = [
        world[0].spherical.lon.to_value(wcs.output_frame.unit[0]),
        world[0].spherical.lon.to_value(wcs.output_frame.unit[1]),
        world[1].to_value(wcs.output_frame.unit[2]),
    ]

    assert not any(isinstance(o, u.Quantity) for o in values)
    np.testing.assert_allclose(values, expected_values)


def test_mismatched_high_level_types(gwcs_3d_identity_units):
    wcs = gwcs_3d_identity_units

    with pytest.raises(
        TypeError,
        match=(
            "Invalid types were passed.*(tuple, SpectralCoord)"
            ".*(SkyCoord, SpectralCoord).*"
        ),
    ):
        wcs.invert((1 * u.deg, 2 * u.deg), coord.SpectralCoord(10 * u.nm))

    # Oh astropy why do you make us do this
    with pytest.raises(
        TypeError,
        match="Invalid types were passed.*got.*Quantity.*expected.*SpectralCoord.*",
    ):
        wcs.invert(coord.SkyCoord(1 * u.deg, 2 * u.deg), 10 * u.nm)
