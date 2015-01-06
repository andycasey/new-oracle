#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Represent and model atomic transitions """

from __future__ import absolute_import, print_function

__all__ = ["AtomicTransition"]
__author__ = "Andy Casey <arc@ast.cam.ac.uk>"

import logging

import numpy as np
from scipy import ndimage, optimize as op

from oracle import synthesis
from oracle.models import profiles
from oracle.specutils import Spectrum1D
from oracle.utils import (atomic_number as parse_atomic_number,
    element as parse_element, overlap)

logger = logging.getLogger("oracle")

class AtomicTransition(object):

    def __init__(self, wavelength, species=None, excitation_potential=None,
        loggf=None, blending_transitions=None, mask=None, continuum_regions=None,
        **kwargs):
        """
        Initialise the class
        """

        self.wavelength = float(wavelength)

        float_if_not_none = lambda x: float(x) if x is not None else x
        self.blending_transitions = np.atleast_2d(blending_transitions) \
            if blending_transitions is not None else None
        self.excitation_potential = float_if_not_none(excitation_potential)
        self.loggf = float_if_not_none(loggf)
        self.mask = mask
        self.van_der_waals_broadening = kwargs.get("van_der_waals_broadening", 0)
        self.continuum_regions = np.atleast_2d(continuum_regions) \
            if continuum_regions is not None else np.array([])

        # Species can be 'Fe I', '26.0', 26.1, 'Fe' (assumed neutral)
        self.element, self.atomic_number, self.ionisation_level, self.species \
            = _parse_species(species)

        self._init_kwargs = kwargs.copy()


    def __str__(self):
        return unicode(self).encode("utf-8").strip()


    def __unicode__(self):
        species_repr = "Unspecified transition" if self.species is None \
            else "{0} {1}".format(self.element, "I" * self.ionisation_level)
        return u"{species_repr} at {wavelength:.1f} Å".format(
            species_repr=species_repr, wavelength=self.wavelength)


    def __repr__(self):
        species_repr = "" if self.species is None else "{0} {1} ".format(
            self.element, "I" * self.ionisation_level)
        # [TODO] astropy.units to show wavelength units
        return "<{module}.AtomicTransition {species_repr}at {wavelength:.1f} "\
            "Angstrom at {location}>".format(module=self.__module__,
                species_repr=species_repr, wavelength=self.wavelength,
                location=hex(id(self)))

    @property
    def reduced_equivalent_width(self):
        """
        Return the reduced equivalent width of the line, if the equivalent width
        has been measured.

        The reduced equivalent width is defined by:

        >> REW = log(equivalent width/wavelength)

        :raise AttributeError:
            If no equivalent width has been measured for this line.
        """

        return np.log(self.equivalent_width/self.wavelength)


    def fit_profile(self, data, initial_theta=None, kind="gaussian", 
        continuum_order=None, continuum_regions=None, surrounding=2,
        detect_nearby_lines=True, constrain_parameters=None, synthesise_kwargs=None,
        optimise_kwargs=None, full_output=False, **kwargs):
        """
        Model and fit the atomic transition with an absorption profile. This
        function can account for continuum, radial velocity offsets (by limiting
        the wavelength range), blending transitions, and outlier pixels.

        While this approach can account for blended lines by synthesising them,
        the user must remember that opacities are not strictly employed properly
        using this method.

        :param data:
            The observed data. This spectrum should include the wavelength of
            the transition.

        :type data:
            :class:`oracle.specutils.Spectrum1D`

        :param initial_theta: [optional]
            Initial estimates of the model parameters :math:`\Theta`. The number
            of model parameters varies depending on the optional inputs, but the
            only common parameter is `line_depth`. The wavelength can
            be a parameter (`wavelength`) if `constrain_parameters` has
            some constraint for `wavelength`, otherwise the wavelength is fixed
            and is not a model parameter.

            The profile parameters will vary depending on the `kind`:

                Gaussian: `fwhm`
                Voigt: `fwhm`, `shape`
                Lorentzian: `scale`

            Where applicable, continuum parameters are represented by
            `continuum.0`, ..., `continuum.N`. If a blending spectrum is to be
            produced (e.g., when `blending_transitions` is not None) then the
            FWHM of the Gaussian kernel to smooth the blending spectrum is
            also a parameter, accessible through `blending_fwhm`.

            :note:
            If `blending_transitions` were supplied to the `AtomicTransition`
            class, then a spectrum will be synthesised. In this situation the
            stellar parameters of the parent model must be provided. These keys
            are `effective_temperature`, `surface_gravity`, `metallicity`, and
            `microturbulence`.

            # Discuss outlier parameters.

        :type initial_theta:
            dict

        :param kind: [optional]
            The kind of profile function to use. Available options are Gaussian,
            Voigt or Lorentzian.

        :type kind:
            str

        :param continuum_order: [optional]
            The order of the polynomial to use to fit the continuum. By default,
            this option is set to None, meaning that no continuum is included.
            In this case the data are assumed to be continuum-normalised (e.g.,
            the absorption begins at unity). Setting this value to zero implies
            one continuum parameter a scaling offset, setting to one implies two
            parameters (ax + b),and so on.

            If continuum is treated, initial values for the continuum can be
            provided by the 'continuum.0', ..., 'continuum.N' keys in
            `initial_theta`.

            Note that if `continuum_regions` are given during initialisation
            then the continuum will be fit to these regions only, and there will
            be no 'continuum.N' parameters in the profile fitting sequence.

        :type continuum_order:
            int

        :param surrounding: [optional]
            The region of spectrum to model either side of the `wavelength`. By
            default this is 1.5 Angstroms.

        :type surrounding:
            float

        :param detect_nearby_lines: [optional]
            Method for treating any outlier pixels. By default no treatment is
            applied. Available options include "fit_nearby".

        :type detect_nearby_lines:
            str

        :param constrain_parameters: [optional]
            Specify constraints for the model parameters. Model parameters are
            expected as keys, and their constraints (lower, upper) are expected
            as values. Use `None` in the lower or upper bound to specify no
            constraint on that edge.

        :type constrain_parameters:
            dict

        :param synthesise_kwargs: [optional]
            Keyword arguments to supply to the synthesise function. This is only
            employed when a blending spectrum is required.

        :type synthesise_kwargs:
            dict

        :param optimise_kwargs: [optional]
            Keyword arguments to supply to the optimisation function.

        :type optimise_kwargs:
            dict

        :param full_output:
            Return additional information about the resulting fit.

        :type full_output:
            bool

        :returns:
            The model parameters.
        """

        if not isinstance(data, Spectrum1D):
            raise TypeError("data must be a oracle.specutils.Spectrum1D object")

        if not (data.disp[-1] > self.wavelength > data.disp[0]):
            raise ValueError("the atomic transition is not in the bounds of the"
                " input data ({0:.0f} outside [{1:.0f}, {2:.0f}])".format(
                    self.wavelength, data.disp[0], data.disp[-1]))

        if initial_theta is None:
            initial_theta = {}

        kind, available = kind.lower(), ("gaussian", "voigt", "lorentzian")
        if kind not in available:
            raise ValueError("available profile types are {}".format(available))

        # [TODO] fix this
        if kind in ("voigt", "lorentzian"):
            raise NotImplementedError("sry gooby")

        if continuum_order is not None:
            try:
                continuum_order = int(continuum_order)
            except (ValueError, TypeError):
                raise TypeError("continuum order must be an integer")
            if continuum_order < 0:
                raise ValueError("continuum order must be a positive integer")

        # Check that the continuum regions are valid
        if self.continuum_regions.size >= 2:
            any_acceptable_continuum_regions = False
            for start, end in self.continuum_regions:
                if overlap(start, end, data.disp[0], data.disp[-1]):
                    any_acceptable_continuum_regions = True
                break

            if not any_acceptable_continuum_regions:
                raise ValueError("continuum regions {0} do not overlap with the"
                    " data [{1:.0f} to {2:.0f}]".format(self.continuum_regions,
                        data.disp[0], data.disp[-1]))
        try:
            surrounding = float(surrounding)
        except (ValueError, TypeError):
            raise TypeError("surrounding region must be a float")
        if surrounding < 0:
            raise ValueError("surrounding region must be a positive float")

        if constrain_parameters is None:
            constrain_parameters = {}
        else:
            # Set lower case keys.
            constrain_parameters = dict((k.lower(), v) \
                for k, v in constrain_parameters.iteritems())

        if synthesise_kwargs is None:
            synthesise_kwargs = {}

        if optimise_kwargs is None:
            optimise_kwargs = {}

        # Establish the fit parameters
        parameters = ["line_depth"]
        profile_parameters = {
            "gaussian": ["fwhm"],
            "lorentzian": ["scale"],
            "voigt": ["fwhm", "shape"]
        }
        parameters.extend(profile_parameters[kind])

        # Is wavelength a free-ish parameter, or completely fixed?
        if "wavelength" in constrain_parameters:
            parameters.append("wavelength")

        # Continuum
        if continuum_order is not None and 2 > self.continuum_regions.size:
            parameters.extend(["continuum.{}".format(i) \
                for i in range(continuum_order + 1)])

        # Blending spectrum FWHM?
        stellar_parameter_keys = ("effective_temperature", "surface_gravity",
            "metallicity", "microturbulence")
        if self.blending_transitions is not None \
        and len(self.blending_transitions) > 0:
            parameters.append("blending_fwhm")

            # Since we have to synthesise a blending spectrum, check that we
            # have the required stellar parameters in initial_theta
            if not all([k in initial_theta for k in stellar_parameter_keys]):
                raise KeyError("stellar parameters ({}) are required for "\
                    "synthesis because this transition has blending transitions"
                    .format(", ".join(stellar_parameter_keys)))

        logger.debug("{0} has {1} parameters: {2}".format(self, len(parameters),
            ", ".join(parameters)))

        # Create a copy of a region of the data and (where applicable,..) apply
        # a mask to the data.
        region = (self.wavelength - surrounding, self.wavelength + surrounding)
        data = data.slice(region, copy=True)
        if self.mask is not None:
            data = data.mask_by_dispersion(self.mask)

        finite = np.isfinite(data.flux)
            
        # Estimate the initial values of parameters that were not given.
        missing_parameters = set(parameters).difference(initial_theta)
        logger.debug("Need to estimate {0} parameters: {1}".format(
            len(missing_parameters), ", ".join(missing_parameters)))

        # Order of estimates (in increasing difficulty)
        # -> wavelength, continuum.N, line_depth, fwhm (et al.), blending_fwhm
        theta = { "wavelength": self.wavelength }
        for parameter in set(parameters).intersection(initial_theta):
            # Use setdefault so we don't overwrite the wavelength
            theta.setdefault(parameter, initial_theta[parameter])

        # Synthesise a blending spectrum if necessary
        if "blending_fwhm" in parameters:
            effective_temperature, surface_gravity, metallicity, microturbulence\
                = [initial_theta[k] for k in stellar_parameter_keys]

            pixel_size = np.diff(data.disp).min()
            synthesise_kwargs.setdefault("oversample", 4)
            synthesise_kwargs.setdefault("wavelength_step", pixel_size)

            blending_spectrum = Spectrum1D(*synthesis.synthesise(
                effective_temperature, surface_gravity, metallicity,
                microturbulence, self.blending_transitions, region[0],
                region[1], **synthesise_kwargs))
        else:
            blending_spectrum = None




        # Here we might have to iterate a little bit on excluding unmodelled
        # lines.

        # Continuum treatment.
        iterate_on_continuum = False
        continuum_mask = np.zeros(data.disp.size, dtype=bool)
        for kk in range(3):

            print(kk, continuum_mask.sum())
            if continuum_order is None:
                # No continuum treatment
                coefficients = [1]

            else:
                # Do we have continuum_regions?
                # If so then we can explicitly set the continuum from the
                # blending_spectrum/or the data.

                # If we don't have continuum_regions then we will need to estimate
                # continuum parameters from blending_spectrum/or the data

                # Do we need to fit for continuum coefficients?
                # We don't if continuum_regions is None and if all the continuum
                # parameters are specified in theta
                if 2 > self.continuum_regions.size and \
                not any([p.startswith("continuum.") for p in missing_parameters]):
                    # Get the input coefficients from initial_theta
                    coefficients = [initial_theta["continuum.{}".format(i)] \
                        for i in range(continuum_order + 1)]

                    # And update theta with these coefficients.
                    theta.update(dict(zip(["continuum.{}".format(i) \
                        for i in range(continuum_order + 1)], coefficients)))

                else:
                    # We need to fit.
                    # Prepare a mask for finite pixels and continuum regions where
                    # appropriate
                    if self.continuum_regions.size >= 2:
                        for start, end in self.continuum_regions:
                            indices = data.disp.searchsorted([start, end])
                            continuum_mask[indices[0]:indices[1]] = True
                        continuum_mask *= finite

                    else:
                        continuum_mask = finite

                    if blending_spectrum is None:
                        # No blending spectrum, just use the data
                        coefficients = np.polyfit(data.disp[continuum_mask],
                            data.flux[continuum_mask], continuum_order)

                        if detect_nearby_lines:
                            iterate_on_continuum = True

                    else:
                        rbs = np.interp(data.disp[continuum_mask],
                            blending_spectrum.disp, blending_spectrum.flux)

                        # Divide with the blending spectrum
                        coefficients = np.polyfit(data.disp[continuum_mask],
                            data.flux[continuum_mask]/rbs, continuum_order)

                        if detect_nearby_lines:
                            iterate_on_continuum = True

                    # Are the coefficients free parameters, or explicitly set?
                    if "continuum.0" in parameters:
                        # Update theta with the coefficients we have estimated
                        theta.update(dict(zip(["continuum.{}".format(i) \
                            for i in range(continuum_order + 1)], coefficients)))


            # Do we need to estimate the line depth?
            if "line_depth" in missing_parameters:
                continuum_at_wavelength = np.polyval(coefficients,
                    self.wavelength)
                index = data.disp.searchsorted(self.wavelength)
                line_depth = 1 - data.flux[index]/continuum_at_wavelength
                
                # Ensure the initial value is limited within a sensible range
                tolerance = kwargs.pop("initial_line_depth_tolerance", 1e-3)
                theta["line_depth"] = np.clip(line_depth, tolerance,
                    1 - tolerance)

            # Do we need to estimate any of the profile parameters?
            # [TODO] here we just do Gaussian because simplicity. Expand on that
            if "fwhm" in missing_parameters:
                mid_flux = continuum_at_wavelength * (1 - 0.5 * theta["line_depth"])

                # Find the wavelengths from the central wavelength where this value
                # exists
                pos_mid_point, neg_mid_point = np.nan, np.nan
                index = data.disp.searchsorted(self.wavelength)
                pos_indices = data.flux[index:] > mid_flux
                if pos_indices.any():
                    pos_mid_point = data.disp[index:][pos_indices][0]

                neg_indices = data.flux[:index] > mid_flux
                if neg_indices.any():
                    neg_mid_point = data.disp[:index][neg_indices][-1]

                # If both positive and negative mid points are nans, then we cannot
                # estimate the FWHM with this method
                if not np.isfinite([pos_mid_point, neg_mid_point]).any():
                    raise ValueError("cannot estimate initial fwhm")

                # If either mid point is a nan, take the initial fwhm from one side
                # of the profile
                initial_fwhm = pos_mid_point - neg_mid_point
                if not np.isfinite(initial_fwhm):
                    initial_fwhm = np.array([
                        2 * (pos_mid_point - self.wavelength),
                        2 * (self.wavelength - neg_mid_point)
                    ])
                    finite = np.isfinite(initial_fwhm)
                    initial_fwhm = initial_fwhm[finite][0]

                theta["fwhm"] = initial_fwhm

                # Do we need to estimate the blending FWHM? If so we will just take it
            # from the initial profile FWHM
            if "blending_fwhm" in missing_parameters:
                theta["blending_fwhm"] = theta["fwhm"]

            # Do we need to update the guess of the continuum?
            if iterate_on_continuum:

                # Create the model given the current initial parameters

                # Smooth the blending spectrum
                if blending_spectrum is not None:
                    fwhm = theta["fwhm"]/np.diff(blending_spectrum.disp).min()
                    blending_spectrum_flux = ndimage.gaussian_filter(
                        blending_spectrum.flux, fwhm/2.355)

                    # Resample to the data dispersion points
                    blending_spectrum_flux = np.interp(data.disp,
                        blending_spectrum.disp, blending_spectrum_flux)
                else:
                    blending_spectrum_flux = np.ones(data.disp.size)

                # Form the absorption profile
                absorption_profile = \
                    1 - theta["line_depth"] * profiles.gaussian(
                        theta.get("wavelength", self.wavelength),
                        theta["fwhm"]/2.355,
                        data.disp)
                continuum = np.polyval(coefficients, data.disp)

                # Put everything together 
                model = blending_spectrum_flux * absorption_profile * continuum

                differences = (model - data.flux)
                differences[~continuum_mask] = 0.
                sigmas = differences/np.std(differences[continuum_mask])

                # Find groups of pixels. Eliminate the top Nth% percent, until
                # the mean sigmas comes in to some tolerance.
                outlier_group_detection_threshold = 1.
                is_outlier = np.abs(sigmas) > outlier_group_detection_threshold
                is_outlier_range_edge = np.where(np.diff(is_outlier))[0]

                # Is the first edge mean we're moving into an outlier range or
                # out of an outlier range
                starts_on_even = abs(sigmas[is_outlier_range_edge[0] + 1]) > \
                    outlier_group_detection_threshold

                for i, index in enumerate(is_outlier_range_edge):
                    # even or odd index?
                    if (i % 2 == 0 and starts_on_even) \
                    or (i % 2 > 0 and not starts_on_even):
                        # Start of section
                        start_index = index
                        end_index = is_outlier_range_edge[i + 1] \
                            if len(is_outlier_range_edge) > i + 1 else None
                        continuum_mask[start_index:end_index] = False


        assert len(set(parameters).difference(theta)) == 0, "Missing parameter!"

        invalid_return = np.nan
        invalid_full_output_return = (np.nan, np.nan, None)
        fixed_continuum = np.polyval(coefficients, data.disp)
        def chi_sq(x, full_output=False, return_scalar=True):

            xd = dict(zip(parameters, x))

            # Physically sensible constraints
            if 0 > xd["fwhm"] or not (1 > xd["line_depth"] > 0) \
            or 0 > xd.get("blending_fwhm", 1):
                return invalid_return \
                    if not full_output else invalid_full_output_return

            # Constraints provided by the user
            for parameter, (lower, upper) in constrain_parameters.iteritems():
                if (lower is not None and lower > xd[parameter]) \
                or (upper is not None and upper < xd[parameter]):
                    return invalid_return \
                        if not full_output else invalid_full_output_return

            # Smooth the blending spectrum
            if blending_spectrum is not None:
                fwhm = xd["blending_fwhm"]/np.diff(blending_spectrum.disp).min()
                blending_spectrum_flux = ndimage.gaussian_filter(
                    blending_spectrum.flux, fwhm/2.355)

                # Resample to the data dispersion points
                blending_spectrum_flux = np.interp(data.disp,
                    blending_spectrum.disp, blending_spectrum_flux)
            else:
                blending_spectrum_flux = np.ones(data.disp.size)

            # Form the absorption profile
            absorption_profile = \
                1 - xd["line_depth"] * profiles.gaussian(
                    xd.get("wavelength", self.wavelength), xd["fwhm"]/2.355,
                    data.disp)

            continuum = fixed_continuum if "continuum.0" not in xd \
                else np.polyval([xd["continuum.{}".format(i)] \
                    for i in range(continuum_order + 1)],
                    data.disp)

            # Put everything together 
            model = blending_spectrum_flux * absorption_profile * continuum

            # Calculate the chi-squared value
            chi_sqs = (model - data.flux)**2 * data.ivariance

            finite = np.isfinite(chi_sqs)
            chi_sq = chi_sqs[finite]

            if return_scalar:
                chi_sq = chi_sq.sum()

            if full_output:
                r_chi_sq = chi_sq / (finite.sum() - len(xd) - 1)
                # Send back some spectra for plotting purposes
                blending_spectrum_continuum = np.polyval(
                    coefficients if "continuum.0" not in xd \
                    else [xd["continuum.{}".format(i)] for i in range(continuum_order + 1)],
                    blending_spectrum.disp)

                return_spectra = {
                    "data_spectrum": data,
                    "continuum_spectrum": Spectrum1D(data.disp, continuum),
                    "blending_spectrum_unsmoothed": Spectrum1D(blending_spectrum.disp,
                        blending_spectrum_continuum * blending_spectrum.flux),
                    "blending_spectrum_smoothed": Spectrum1D(data.disp,
                        continuum * blending_spectrum_flux),
                    "fitted_spectrum": Spectrum1D(data.disp, model),
                }
                return (chi_sq, r_chi_sq, return_spectra)
            return chi_sq

        minimisation_function = chi_sq

        # Check for any violations in the initial parameters
        p0 = np.array([theta[p] for p in parameters])
        if (~np.isfinite(p0)).any():
            raise ValueError("non-finite initial value")

        try:
            # initial chi-sq, initial reduced chi-sq, initial model fit
            ic, irc, imf = minimisation_function(p0, full_output=True)

        except:
            logger.exception("Exception raised when trying to start profile "
                "fitting:")
            raise

        else:
            if not np.isfinite(ic) or ic == invalid_return:
                raise ValueError("invalid value returned by minimisation "
                    "function when initial theta values were provided")

        # [TODO] Allow for something other than ye-olde Nelder & Meade?
        op_info = { "p0": theta }
        op_kwargs = optimise_kwargs.copy()
        op_kwargs["full_output"] = True
        op_kwargs["xtol"] = 1e-5
        op_kwargs["ftol"] = 1e-5
        op_kwargs.setdefault("disp", False)
        #p1, cov_x, op_info, mesg, ier = op.leastsq(
        
        p1, fopt, num_iter, num_funcalls, warnflag = op.fmin(
            minimisation_function, p0, **op_kwargs)

        # Get all our information together
        optimal_theta = dict(zip(parameters, p1))
        oc, orc, op_spectra = minimisation_function(p1, full_output=True)
        profile_integrals = {
            # Other profile functions will probably need additional information
            # other than just 'x' (the optimal dictionary)
            # For those playing at home: pi^2/2.355 == 0.752634331594699
            "gaussian": lambda x: x["line_depth"] * abs(x["fwhm"]) * 0.752634332
        }
        # Calculate the equivalent width (in milli Angstroms)
        # [TODO] use astropy.units to provide some relative measure
        self.equivalent_width = 1000 * profile_integrals[kind](optimal_theta)

        op_info.update({
            "chi_sq": oc,
            "r_chi_sq": orc,
            "fopt": fopt,
            "num_iter": num_iter,
            "num_funcalls": num_funcalls,
            "warnflag": warnflag,
            "profile_kind": kind,
            "equivalent_width": self.equivalent_width
        })
        op_info.update(op_spectra)
        
        self._profile = (optimal_theta, op_info)

        # Any sanity checks?
        if "blending_fwhm" in optimal_theta:
            fwhm_change = optimal_theta["blending_fwhm"]/optimal_theta["fwhm"]
            if not (2 > fwhm_change > 0.5):
                logging.debug("Profile and blending FWHM differ substantially "
                    "from each other: profile_fwhm = {0:.2f} Angstrom, blending"
                    "_fwhm = {1:.2f}".format(optimal_theta["fwhm"],
                        optimal_theta["blending_fwhm"]))

        # What information should we save to the class?
        self._profile = (optimal_theta, op_info)

        if full_output:
            return (optimal_theta, oc, orc, op_info)

        # I could not sleep for 65 days because I worried about whether I should
        # be returning a list of values or a dictionary by default. In the end I
        # decided that since the length (and order) of model parameters can vary
        # depending on the input keywords, and that the model parameters are not
        # easily accessible, I should return a dictionary here to be 'explicit'.

        # (The above paragraph pleases my OCD)

        return optimal_theta


def _parse_ionisation_level(ionisation_level):
    """
    Common imputs:
    1, 2, I, II
    """

    if isinstance(ionisation_level, int):
        return ionisation_level

    # String assumed
    ionisation_level = ionisation_level.upper()
    if "I" in ionisation_level:
        # Assuming less than ionisation state 4 (e.g., IV)
        return ionisation_level.count("I")
    return int(ionisation_level)


def _parse_species(species):

    if species is None:
        # No idea.
        return (None, None, None, None)

    try:
        # Float species are easiest
        species = float(species)

    except (ValueError, TypeError):
        # Element string representations are the only thing that we will accept
        # now

        atomic_number = parse_atomic_number(species)
        element = parse_element(atomic_number)

        # Unless provided, ground state is assumed.
        ionisation_level = _parse_ionisation_level(species.split()[1]) \
            if " " in species else 1

        species = atomic_number + ionisation_level/10.
        return (element, atomic_number, ionisation_level, species)


    else:
        element = parse_element(species)
        atomic_number = int(species)
        ionisation_level = int(10 * (species - atomic_number)) + 1
        
    return (element, atomic_number, ionisation_level, species)
        