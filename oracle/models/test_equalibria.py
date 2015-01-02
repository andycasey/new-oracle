
import os
import oracle


def equalibria():
    data = [
        oracle.specutils.Spectrum1D.load("Spectra/ccd_1/sun_blu.0002.fits"),
        oracle.specutils.Spectrum1D.load("Spectra/ccd_2/sun_grn.0002.fits"),
        oracle.specutils.Spectrum1D.load("Spectra/ccd_3/sun_red.0002.fits"),
        oracle.specutils.Spectrum1D.load("Spectra/ccd_4/sun_ir.0002.fits"),
    ]

    model = oracle.models.EqualibriaModel({
            "model": {
                "redshift": True,
                "instrumental_resolution": True,
                "continuum": 2,
                "atomic_transitions": [
                    {  
                        "wavelength": 4720.1489,
                        "species": 26.1,
                        "excitation_potential": 3.197,
                        "loggf": -4.48,
                        "blending_transitions": None,
                        "mask": None
                    },
                    # wavelength, species, chi, loggf, damp1, damp2, synthesise_surrounding, opacity_contribution
                    #[4720.1489, 26.1, 3.197, -4.48],
                    [4731.4531, 26.1, 2.891, -3.1],
                    [4788.7568, 26.0, 3.237, -1.763],
                    [4793.9619, 26.0, 3.047, -3.43],
                    [4794.3599, 26.0, 2.424, -3.95],
                    [4802.8799, 26.0, 3.642, -1.51],
                    [4808.1479, 26.0, 3.251, -2.69],
                    [4833.1968, 26.1, 2.657, -5.11],
                    [4890.7588, 26.0, 2.875, -0.394],
                    [4891.4922, 26.0, 2.851, -0.111],
                    [5651.4692, 26.0, 4.473, -1.9],
                    [5652.3179, 26.0, 4.26, -1.85],
                    [5661.3462, 26.0, 4.284, -1.756],
                    [5679.0229, 26.0, 4.652, -0.82],
                    [5680.2402, 26.0, 4.186, -2.48],
                    [5696.0898, 26.0, 4.548, -1.72],
                    [5705.4648, 26.0, 4.301, -1.355],
                    [5731.7622, 26.0, 4.256, -1.2],
                    [5732.2959, 26.0, 4.991, -1.46],
                    [5741.8481, 26.0, 4.256, -1.672],
                    [5775.0811, 26.0, 4.22, -1.297],
                    [5778.4531, 26.0, 2.588, -3.43],
                    [5849.6841, 26.0, 3.694, -2.89],
                    [5853.1479, 26.0, 1.485, -5.18],
                    [5855.0771, 26.0, 4.608, -1.478],
                    [5858.7778, 26.0, 4.22, -2.16],
                    [6481.8701, 26.0, 2.279, -2.981],
                    [6494.98, 26.0, 2.404, -1.256],
                    [6498.939, 26.0, 0.958, -4.687],
                    [6508.8501, 20.0, 2.526, -2.408],
                    [6516.0801, 26.1, 2.891, -3.31],
                    [6518.3672, 26.0, 2.831, -2.438],
                    [6546.2388, 26.0, 2.758, -1.536],
                    [6592.9141, 26.0, 2.727, -1.473],
                    [6593.8701, 26.0, 2.433, -2.42],
                    [6597.561, 26.0, 4.795, -0.97],
                    [6609.1099, 26.0, 2.559, -2.691],
                    [6627.5449, 26.0, 4.548, -1.59],
                    [6648.0801, 26.0, 1.011, -5.918],
                    [6677.9868, 26.0, 2.692, -1.418],
                    [6699.1421, 26.0, 4.593, -2.101],
                    [6703.5669, 26.0, 2.758, -3.06],
                    [6713.7451, 26.0, 4.795, -1.5],
                    [6733.1509, 26.0, 4.638, -1.48],
#                    [6739.521, 26.0, 1.557, -4.794],
                    [7710.3638, 26.0, 4.22, -1.113],
                    [7711.7231, 26.1, 3.903, -2.5],
                    [7723.21, 26.0, 2.2786, -3.617],
                    [7748.269, 26.0, 2.949, -1.751]
                ]
    #            "atomic_lines_filename": "test_atomic_lines.txt"
    #            "blending_lines_filename": "test_blen"
            },
            "settings": {
                "threads": 4
            }
        })


    theta = model.initial_theta(data)

    stellar_parameters = model.estimate_stellar_parameters(data,
        initial_theta=theta)

    raise a

# Don't run this test on Travis.
if "TRAVIS_BUILD_ID" not in os.environ:
    equalibria()