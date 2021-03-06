#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Solvers to fit atomic absorption transitions. """

from __future__ import absolute_import, print_function

__author__ = "Andy Casey <arc@ast.cam.ac.uk>"
__all__ = ["ProfileFitter", "ProfileMixtureFitter"]

import logging
import numpy as np

from scipy import optimize as op

from .base import BaseFitter
from .profile_functions import gaussian, voigt

logger = logging.getLogger("oracle")


class ProfileFitter(BaseFitter):
    """
    Fit absorption profiles to semi-normalised, near-rest-frame spectra.
    """

    def __init__(self, global_continuum=False, global_resolution=False, **kwargs):
        """
        Fit profiles to absorption lines.
        """

        self._default_kwargs = {
            "mask": [],
            "profile": "gaussian",
            "initial_fwhm": 0.10,
            "central_weighting": True,
            "wavelength_tolerance": 0.10,
            "continuum_degree": 0,
            "maximum_wavelength_window": 1.0,
            "clip_model_sigma": 0.0,
        }
        self._default_kwargs.update(**kwargs)
        self.global_continuum = global_continuum
        self.global_resolution = global_resolution

        if self._default_kwargs["profile"].lower() not in ("gaussian", "voigt"):
            raise ValueError("profile must be either gaussian or a voigt")

        if 0 >= self._default_kwargs["initial_fwhm"]:
            raise ValueError("initial FWHM value must be positive")

        if 0 > self._default_kwargs["wavelength_tolerance"]:
            raise ValueError("wavelength tolerance must be zero or positive")

        return None


    def fit(self, spectrum, wavelength, mask=None, **kwargs):

        full_output = kwargs.pop("full_output", False)

        # Get the keywords.
        kwds = self._default_kwargs.copy()
        kwds.update(**kwargs)

        if mask is not None:
            # Join the masks so we only have to deal with one.
            kwds["global_mask"].extend(mask)

        f = np.isfinite(spectrum.flux)
        if not (spectrum.disp[f][-1] > wavelength > spectrum.disp[f][0]):
            raise ValueError("wavelength {0:.2f} Angstroms is outside of the "\
                "observed finite spectral range ({1:.2f}, {2:.2f})".format(
                    wavelength, spectrum.disp[f][0], spectrum.disp[f][-1]))

        # Get the index of the profile trough.
        if kwds["wavelength_tolerance"] > 0:
            # Look for the lowest flux point between wavelength +/- tolerance.
            idxs = spectrum.disp.searchsorted([
                wavelength - kwds["wavelength_tolerance"],
                wavelength + kwds["wavelength_tolerance"]
            ])
            index = np.nanargmin(spectrum.flux.__getslice__(*idxs)) + idxs[0]
        else:
            index = spectrum.disp.searchsorted(wavelength)

        # What wavelength range will actually be fit?
        indices = spectrum.disp.searchsorted([
            wavelength - kwds["maximum_wavelength_window"],
            wavelength + kwds["maximum_wavelength_window"]
        ])

        disp = spectrum.disp.__getslice__(*indices).copy()
        flux = spectrum.flux.__getslice__(*indices).copy()
        variance = spectrum.variance.__getslice__(*indices).copy()

        # Scale the variance by distance from the centroid?
        if kwds["central_weighting"]:
            variance *= 4 * np.abs(disp - wavelength)**2

        # Apply any masks.
        mask = self.mask_data(disp, flux / variance, kwds["global_mask"],
            mask_non_finites=True)

        if 5 > (~mask).sum(): # minimum 5 pixels
            # No finite data around the line.
            raise ValueError("no finite data within {0:.2f} Angstroms of the "\
                "line at {1:.2f} Angstroms".format(kwds["wavelength_tolerance"],
                    wavelength))

        # Get the profile and initialise the point.
        trough_point = 1 - spectrum.flux[index]
        try:
            contains_fwhm = 1 - trough_point/2. >= flux
            idx = np.where(contains_fwhm)[0]
            initial_fwhm = disp[np.diff(idx).nonzero()].ptp()

        except ValueError:
            initial_fwhm = kwds["initial_fwhm"]
            logger.exception("Exception in calculating initial FWHM for line at"
                " {0:.3f} Angstroms".format(wavelength))

        initial_fwhm = np.clip(initial_fwhm, 0, 5 * kwds["initial_fwhm"])

        p_init = np.array([
            spectrum.disp[index],   # mu
            initial_fwhm / 2.355,   # sigma
            trough_point            # amplitude
        ])
        if kwds["profile"] == "gaussian":
            p = gaussian() 
            
        elif kwds["profile"] == "voigt":
            p = voigt()
            p_init = np.append(p_init, [0.01]) # shape
        

        # Continuum.
        continuum_degree = kwds["continuum_degree"]
        if continuum_degree > 0:
            coefficients = np.zeros(continuum_degree)
            coefficients[-1] = 1.0
            p_init = np.append(p_init, coefficients)

            f = lambda x, *a: np.polyval(a[-continuum_degree:], x) * p(x, *a)

        else:
            f = lambda x, *a: p(x, *a)

        def g(x, *a):
            mu, sigma, amplitude = a[:3]
            if (kwds["wavelength_tolerance"] > 0 \
            and np.abs(mu - wavelength) > kwds["wavelength_tolerance"]) \
            or 0 >= sigma or not (1 >= amplitude >= 0):
                return np.inf * np.ones_like(x)
            return f(x, *a)

        try:
            # Note: Ensure we are only using finite values for the fit.
            p_opt, p_cov = op.curve_fit(g, disp[~mask], flux[~mask], p_init,
                sigma=np.sqrt(variance[~mask]), absolute_sigma=True, epsfcn=0.0,
                ftol=1e-10, gtol=1e-10)

        except:
            logger.exception("Exception occurred during line-fitting (1):")
            raise

        # Clip pixels that are >4 sigma away.
        if kwds["clip_model_sigma"] > 0:

            model_sigma = np.abs((flux - f(disp, *p_opt))/np.sqrt(variance))
            mask_b = mask * (model_sigma >= kwds["clip_model_sigma"])

            try:
                # Note: Ensure we are only using finite values for the fit.
                p_opt, p_cov = op.curve_fit(g, disp[~mask_b], flux[~mask_b], p_init,
                    sigma=np.sqrt(variance[~mask_b]), absolute_sigma=True,
                    epsfcn=0.0, ftol=1e-10, gtol=1e-10)

            except:
                logger.exception("Exception occurred during line-fitting (2):")
                raise

        # Calculate the equivalent width.
        equivalent_width = f.integrate(*p_opt)

        if full_output:
            return (equivalent_width, p_opt, p_init, kwds,
                [disp[~mask], f(disp[~mask], *p_opt), f(disp[~mask], *p_init)], p_cov)

        return (equivalent_width, p_opt, kwds)



    def fit_all_transitions(self, spectrum, wavelengths, masks=None, **kwargs):
        """
        Fit profiles to all the transitions, then use the information about the
        transitions to identify poorly fit lines.
        """
        raise NotImplementedError









class ProfileMixtureFitter(ProfileFitter):

    def fit(self, spectrum, wavelength, mask=None, **kwargs):

        full_output = kwargs.pop("full_output", False)

        # Get the keywords.
        kwds = self._default_kwargs.copy()
        kwds.update(**kwargs)

        if mask is not None:
            # Join the masks so we only have to deal with one.
            kwds["global_mask"].extend(mask)

        f = np.isfinite(spectrum.flux)
        if not (spectrum.disp[f][-1] > wavelength > spectrum.disp[f][0]):
            raise ValueError("wavelength {0:.2f} Angstroms is outside of the "\
                "observed finite spectral range ({1:.2f}, {2:.2f})".format(
                    wavelength, spectrum.disp[f][0], spectrum.disp[f][-1]))

        # Get the index of the profile trough.
        if kwds["wavelength_tolerance"] > 0:
            # Look for the lowest flux point between wavelength +/- tolerance.
            idxs = spectrum.disp.searchsorted([
                wavelength - kwds["wavelength_tolerance"],
                wavelength + kwds["wavelength_tolerance"]
            ])
            index = np.nanargmin(spectrum.flux.__getslice__(*idxs)) + idxs[0]
        else:
            index = spectrum.disp.searchsorted(wavelength)

        # What wavelength range will actually be fit?
        indices = spectrum.disp.searchsorted([
            wavelength - kwds["maximum_wavelength_window"],
            wavelength + kwds["maximum_wavelength_window"]
        ])

        disp = spectrum.disp.__getslice__(*indices)
        flux = spectrum.flux.__getslice__(*indices)
        variance = spectrum.variance.__getslice__(*indices)

        # Apply any masks.
        ma = self.mask_data(disp, flux / variance, kwds["global_mask"],
            mask_non_finites=True)

        if 5 > (ma).sum(): # minimum 5 pixels
            # No finite data around the line.
            raise ValueError("no finite data within {0:.2f} Angstroms of the "\
                "line at {1:.2f} Angstroms".format(kwds["wavelength_tolerance"],
                    wavelength))

        # Get the profile and initialise the point.
        trough_point = 1 - spectrum.flux[index]
        try:
            contains_fwhm = 1 - trough_point/2. >= flux
            idx = np.where(contains_fwhm)[0]
            initial_fwhm = disp[np.diff(idx).nonzero()].ptp()

        except ValueError:
            initial_fwhm = kwds["initial_fwhm"]
            logger.exception("Exception in calculating initial FWHM for line at"
                " {0:.3f} Angstroms".format(wavelength))

        initial_fwhm = np.clip(initial_fwhm, 0, 5 * kwds["initial_fwhm"])

        p_init = np.array([
            spectrum.disp[index],   # mu
            initial_fwhm / 2.355,   # sigma
            trough_point,           # amplitude
        ])
        if kwds["profile"] == "gaussian":
            f = gaussian() 
            
        elif kwds["profile"] == "voigt":
            f = voigt()
            p_init = np.append(p_init, [0.01]) # shape
        
        # Add outlier treatment.
        p_init = np.append(p_init, [
            0.01,                   # outlier fraction
            np.mean(flux[ma]),      # outlier mean
            0.01                    # Outlier variance
            ])
        

        def nlp(a, disp, flux, variance):
            mu, sigma, amplitude = a[:3]
            P, Y, V = a[-3:]

            if (kwds["wavelength_tolerance"] > 0 \
            and np.abs(mu - wavelength) > kwds["wavelength_tolerance"]) \
            or 0 >= sigma or not (1 >= amplitude >= 0) \
            or not (1 > P > 0) or 0 > V:
                return np.inf

            model = f(disp, *a[:-3])
            background_model = Y

            # Calculate negative log-likelihood.
            ivar_model = 1./variance
            ivar_background = 1./(V + variance)

            lnlike_model = -0.5 * ((flux - model)**2 \
                * ivar_model - np.log(ivar_model))
            lnlike_background = -0.5 * ((flux - background_model)**2 \
                * ivar_background - np.log(ivar_background))

            return -np.sum(np.logaddexp(np.log(1-P) + lnlike_model,
                np.log(P) + lnlike_background))

        """
        try:
            # Note: Ensure we are only using finite values for the fit.
            p_opt, p_cov = op.curve_fit(g, disp[ma], flux[ma], p_init,
                sigma=np.sqrt(variance[ma]), absolute_sigma=True)
        """

        try:
            p_opt = op.fmin(nlp, p_init,
                args=(disp[ma], flux[ma], variance[ma]), disp=False)
            p_cov = None

        except:
            logger.exception("Exception occurred during line fitting procedure.")
            raise

        # Calculate the equivalent width.
        equivalent_width = f.integrate(*p_opt[:-3])

        if full_output:
            return (equivalent_width, p_opt, p_init, kwds,
                [disp[ma], f(disp[ma], *p_opt[:-3]), f(disp[ma], *p_init[:-3])], p_cov)

        return (equivalent_width, p_opt, kwds)






if __name__ == "__main__":

    import oracle

    a = oracle.specutils.Spectrum1D.load_GALAH(
        "/Users/arc/research/galah/data/iDR1/data/benchmark/DeltaEri_3.fits", normalised=True, rest=True)

    b = oracle.specutils.Spectrum1D.load_GALAH(
        "/Users/arc/research/galah/data/iDR1/data/benchmark/18Sco_3.fits", normalised=True, rest=True)


    spec = b

    from astropy.table import Table
    line_list = Table.read("/Users/arc/research/galah/data/iDR1/line-list.txt", format="ascii")


    fitter = ProfileFitter(profile="gaussian")
    #fitter.fit(spec, 4779.29, mask=[[4779.6, 6000]])


    # Measure them lines all in the normalised benchmark spectra
    # Make plots of all measured lines. How do they look?

    for i, line in enumerate(line_list):
        try:
            ew, p_opt, p_init, kwds, (disp, flux, flux_init), cov = fitter.fit(spec, line["wavelength"], full_output=True)

        except ValueError:
            continue


        else:
            print(p_opt)
            fig, ax = plt.subplots()

            ax.plot(disp, flux, c='r', zorder=100)
            ax.plot(disp, flux_init, c='b')
            ax.plot(spec.disp, spec.flux, c='k')
            ax.fill_between(spec.disp, spec.flux - spec.variance**0.5,
                spec.flux + spec.variance**0.5, facecolor="#cccccc")
            ax.set_xlim(disp[0], disp[-1])
            ax.set_ylim(0, 1.2)
            ax.axvline(line["wavelength"])

            fig.savefig("test-{}.png".format(i))
            plt.close("all")



    # Implement synthesis properly in mini-MOOG, as was done for myabfind.f
    # Implement a synthesiser class that can be used in the line fitting thing
    # Implement way to be able to set up an exictation balance with the synthesis fitter.

    # Implement Strong lines in mini-MOOG.
    # Test balmer line synthesis in MOOG -- how does it compare to hlinprof?

    # Do excitation/ionisation balance on the Sun using the measured lines + 1D MARCS
    # Do excitation/ionisation balance on the Sun using the measured lines + <3D>

    # Implement a GUI to be able to easily setup line lists, masks, etc and test
    # a thing.



    # WG11 fix microturbulence values
    # WG10 include bulge data
