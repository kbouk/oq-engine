# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2015-2018 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

"""
Module exports :class:`ParkerEtAl2020SInter`
               :class:`ParkerEtAl2020SInterAleutian`
               :class:`ParkerEtAl2020SInterAlaska`
               :class:`ParkerEtAl2020SInterCascadiaOut`
               :class:`ParkerEtAl2020SInterCascadiaSeattle`
               :class:`ParkerEtAl2020SInterCascadia`
               :class:`ParkerEtAl2020SInterCAMN`
               :class:`ParkerEtAl2020SInterCAMS`
               :class:`ParkerEtAl2020SInterJapanPac`
               :class:`ParkerEtAl2020SInterJapanPhi`
               :class:`ParkerEtAl2020SInterSAN`
               :class:`ParkerEtAl2020SInterSAS`
               :class:`ParkerEtAl2020SInterTaiwanE`
               :class:`ParkerEtAl2020SInterTaiwanW`
               :class:`ParkerEtAl2020SSlab`
               :class:`ParkerEtAl2020SSlabAleutian`
               :class:`ParkerEtAl2020SSlabAlaska`
               :class:`ParkerEtAl2020SSlabCascadiaOut`
               :class:`ParkerEtAl2020SSlabCascadiaSeattle`
               :class:`ParkerEtAl2020SSlabCascadia`
               :class:`ParkerEtAl2020SSlabCAMN`
               :class:`ParkerEtAl2020SSlabCAMS`
               :class:`ParkerEtAl2020SSlabJapanPac`
               :class:`ParkerEtAl2020SSlabJapanPhi`
               :class:`ParkerEtAl2020SSlabSAN`
               :class:`ParkerEtAl2020SSlabSAS`
               :class:`ParkerEtAl2020SSlabTaiwanE`
               :class:`ParkerEtAl2020SSlabTaiwanW`
"""
import math

import numpy as np
import pandas as pd

from openquake.hazardlib.gsim.base import GMPE, CoeffsTable
from openquake.hazardlib import const
from openquake.hazardlib.imt import PGA, SA, PGV


class ParkerEtAl2020SInter(GMPE):
    """
    Implements Parker et al. (2020) for subduction interface.
    """

    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.SUBDUCTION_INTERFACE

    #: Supported intensity measure types are spectral acceleration,
    #: peak ground acceleration and peak ground velocity
    DEFINED_FOR_INTENSITY_MEASURE_TYPES = set([
        PGV,
        PGA,
        SA
    ])

    #: Supported intensity measure component is the geometric mean component
    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.AVERAGE_HORIZONTAL

    #: Site amplification is dependent only upon Vs30
    REQUIRES_SITES_PARAMETERS = {'vs30'}

    #: Required rupture parameters are only magnitude for the interface model
    REQUIRES_RUPTURE_PARAMETERS = {'mag'}

    #: Required distance measure is closest distance to rupture, for
    #: interface events
    REQUIRES_DISTANCES = {'rrup'}

    def __init__(self, region=None, saturation_region=None, basin=None):
        super().__init__()
        self.region = region
        if saturation_region is None:
            self.saturation_region = region
        else:
            self.saturation_region = saturation_region
        self.basin = basin

    def get_mean_and_stddevs(self, sites, rup, dists, imt, stddev_types):
        """
        
        """
        # extract dictionaries of coefficients specific to required
        # intensity measure type and for PGA
        C = self.COEFFS[imt]
        C_PGA = self.COEFFS[PGA()]
        
        Mb = self._get_mb()
        c0, c0_pga = self._c0(C, C_PGA)
        Fm, Fm_pga = self._magnitude_scaling(C, C_PGA, rup.mag, Mb)
        Fp, Fp_pga = self._path_term(C, C_PGA, rup.mag, dists.rrup, Mb)
        Fd = self._depth_scaling(C, rup.hypo_depth)
        Fd_pga = self._depth_scaling(C_PGA, rup.hypo_depth)
        Fb = self._basin_term(C, sites, basin)
        Flin = self._linear_amplification(C, sites.vs30)
        Fnl = self._non_linear_term(C, imt, vs30, Fp_pga, Fm_pga, c0_pga, Fd_pga)
        
        # The output is the desired median model prediction in LN units
        # Take the exponential to get PGA, PSA in g or the PGV in cm/s
        mu = Fp + Fnl + Fb + Flin + Fm + c0 + Fd
        return mu

    def hypocentral_depth_estimate(self, ztor, width, dip):
        """
        Estimate hypocentral_depth if not available.
        Ch. 4.3.3/Eqs. 4.16 & 4.17  of Parker et al. (2020).
        """
        return ztor + 0.48 * width * math.sin(dip)

    def _c0(self, C, C_PGA):
        # c0
        if self.saturation_region is None:
            c0_col = "c0"
        else:
            c0_col = self.saturation_region + "_c0"
        return C[c0_col], C_PGA[c0_col]

    def _magnitude_scaling(self, C, C_PGA, mag, Mb):
        m_diff = mag - Mb
        if m_diff > 0:
            Fm = C["c6"] * m_diff
            Fm_pga = C_PGA["c6"] * m_diff
        else:
            Fm = C["c4"] * m_diff + C["c5"] * m_diff ** 2
            Fm_pga = C_PGA["c4"] * m_diff + C_PGA["c5"] * m_diff ** 2

    def _get_mb(self):
        mb_regions = ("Aleutian", "AK", "Cascadia", "CAM_S", "CAM_N", \
            "JP_Pac", "JP_Phi", "SA_N", "SA_S", "TW_W", "TW_E")
        if self.saturation_region in mb_regions:
            i = mb_regions.index(self.saturation_region)
            Mb = (8, 8.6, 7.7, 7.4, 7.4, 8.5, 7.7, 8.5, 8.6, 7.1, 7.1)[i]
        else:
            Mb = 7.9

        return Mb

    def _path_term_h(self, mag, Mb=None):
        return 10 ** (-0.82 + 0.252 * mag)

    def _a0(self, C, C_PGA, region):
        # isolate regional anelastic coefficient, a0
        if region is None or (region == "Cascadia" and not slab):
            a0 = C["a0"]
            a0_pga = C_PGA["a0"]
        else:
            a0 = C[region + "_a0"]
            a0_pga = C_PGA[region + "_a0"]

    def _path_term(self, C, C_PGA, mag, rrup, Mb):
        # path term
        h = self._path_term_h(self, mag, Mb)
        R = math.sqrt(rrup ** 2 + h ** 2)
        # log(R / Rref)
        R_Rref = math.log(R / math.sqrt(1 + h ** 2))

        a0, a0_pga = self._a0(C, C_PGA, self.region)

        Fp = C["c1"] * math.log(R) + (self.CONSTANTS["b4"] * mag) \
            * R_Rref + a0 * R
        Fp_pga = C_PGA["c1"] * math.log(R) + (self.CONSTANTS["b4"] * mag) \
            * R_Rref + a0_pga * R

        return Fp, Fp_pga

    def _linear_amplification(self, C, vs30):
        # site coefficients
        V1 = self.CONSTANTS["V1"]
        Vref = self.CONSTANTS["Vref"]
        if self.region is None or self.region == "CAM":
            s2 = C["s2"]
            s1 = s2
        elif self.region == "TW" or self.region == "JP":
            s2 = C[self.region + "_s2"]
            s1 = C[self.region + "_s1"]
        else:
            s2 = C[self.region + "_s2"]
            s1 = s2

        # linear site term
        if vs30 <= V1:
            return s1 * math.log(vs30 / V1) + s2 * math.log
        elif vs30 <= C["V2"]:
            return s2 * math.log(vs30 / Vref)
        else:
            return s2 * math.log(C["V2"] / Vref)

    def _non_linear_term(self, C, imt, vs30, fp, fm, c0, fd=0):
        # non-linear site term
        # Fd for slab only
        PGAr = math.exp(Fp_pga + Fm_pga + c0_pga + Fd_pga)

        if imt not in ["pga", "pgv"] and imt >= 3:
            Fnl = 0
        else:
            Fnl = C["f4"] * (math.exp(C["f5"] \
                * (min(vs30, self.CONSTANTS["Vref_Fnl"]) \
                - self.CONSTANTS["Vb"])) - math.exp(C["f5"] \
                * (self.CONSTANTS["Vref_Fnl"] - self.CONSTANTS["Vb"])))
            Fnl *= math.log((PGAr \
                + self.CONSTANTS["f3"]) / self.CONSTANTS["f3"])

        return Fnl

    def _basin_term(self, C, sites=None):
        """
        Basin term main handler.
        """
        if sites is None or sites.z2pt5 is None:
            return 0

        if self.region == "JP":
            return self._get_basin_term_factors(3.05, -0.8, 500, 0.33, \
                C["J_e1"], C["J_e2"], C["J_e3"])

        elif self.region == "Cascadia":
            if self.basin is None:
                return self._get_basin_term_factors(3.94, -0.42, 200, 0.2, \
                    C["C_e1"], C["C_e2"], C["C_e3"], sites)
            elif self.basin == "out":
                dn = C["del_None"]
                return self._get_basin_term_factors(3.94, -0.42, 200, 0.2, \
                    C["C_e1"] + dn, C["C_e2"] + dn, C["C_e3"] + dn, sites)
            elif self.basin == "Seattle":
                ds = C["del_Seattle"]
                return self._get_basin_term_factors(3.94, -0.42, 200, 0.2, \
                    C["C_e1"] + ds, C["C_e2"] + ds, C["C_e3"] + ds, sites)

        return 0

    def _get_basin_term_factors(self, theta0, thea1, vmu, vsig, e1, e2, e3, \
            sites):
        """
        Basin term for given factors.
        """
        Z2p5_pred = 10 ** (theta0 + theta1 \
            * (1 + math.erf((math.log10(sites.vs30) - math.log10(vmu)) \
            / (vsig * math.sqrt(2)))))
        del_Z2p5 = math.log(sites.z2pt5) - math.log(Z2p5_pred)

        if del_Z2p5 <= (e1 / e3):
            return e1
        elif del_Z2p5 >= (e2 / e3):
            return e2
        else:
            return e3 * del_Z2p5

    def _depth_scaling(self, C, hypo_depth):
        return 0

    # sa_damping required but significance of 5 unknown
    COEFFS = CoeffsTable(sa_damping=5, table="""\
    IMT    c0    AK_c0        Aleutian_c0  Cascadia_c0 CAM_N_c0     CAM_S_c0    JP_Pac_c0    JP_Phi_c0    SA_N_c0     SA_S_c0      TW_E_c0      TW_W_c0     c0slab AK_c0slab Aleutian_c0slab Cascadia_c0slab CAM_c0slab JP_c0slab SA_N_c0slab SA_S_c0slab TW_c0slab  c1     c1slab b4   a0        AK_a0     CAM_a0    JP_a0     SA_a0     TW_a0     a0slab    AK_a0slab Cascadia_a0slab CAM_a0slab JP_a0slab SA_a0slab TW_a0slab c4     c5    c6    c4slab c5slab c6slab d      m      db   V2  JP_s1  TW_s1  s2     AK_s2  Cascadia_s2 JP_s2  SA_s2  TW_s2  f4       f4slab   f5       J_e1   J_e2   J_e3  C_e1   C_e2   C_e3   del_None del_Seattle Tau   phi21 phi22  phi2V  VM phi2S2S,0 a1    phi2SS,1 phi2SS,2 a2
    pgv    8.097 9.283796298  8.374796298  7.728       7.046899908  7.046899908 8.772125851  7.579125851  8.528671414 8.679671414  7.559846279  7.559846279 13.194 12.79     13.6            12.874          12.81      13.248    12.754      12.927      13.516    -1.661 -2.422  0.1 -0.00395  -0.00404  -0.00153  -0.00239  -0.000311 -0.00514  -0.0019   -0.00238  -0.00109        -0.00192   -0.00215  -0.00192   -0.00366  1.336 -0.039 1.844 1.84  -0.05   0.8    0.2693 0.0252 67  850 -0.738 -0.454 -0.601 -1.031 -0.671      -0.738 -0.681 -0.59  -0.31763 -0.31763 -0.0052  -0.137  0.137  0.091 0      0.115  0.068 -0.115    0           0.477 0.348 0.288 -0.179 423 0.142     0.047 0.153    0.166    0.011
    pga    4.082 4.458796298  3.652796298  3.856       2.875899908  2.875899908 5.373125851  4.309125851  5.064671414 5.198671414  3.032846279  3.032846279  9.907  9.404     9.912           9.6             9.58      10.145     9.254       9.991      10.071    -1.662 -2.543  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00227  -0.00354        -0.00238   -0.00335  -0.00238   -0.00362  1.246 -0.021 1.128 1.84  -0.05   0.4    0.3004 0.0314 67 1350 -0.586 -0.44  -0.498 -0.785 -0.572      -0.586 -0.333 -0.44  -0.44169 -0.44169 -0.0052   0      0      1     0      0      1      0        0           0.48  0.396 0.565 -0.18  423 0.221     0.093 0.149    0.327    0.068
    0.01   3.714 4.094796298  3.288796298  3.488       2.564899908  2.564899908 5.022125851  3.901125851  4.673671414 4.807671414  2.636846279  2.636846279  9.962  9.451     9.954           9.802           9.612     10.162     9.293       9.994      10.174    -1.587 -2.554  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.246 -0.021 1.128 1.84  -0.05   0.4    0.2839 0.0296 67 1300 -0.604 -0.44  -0.498 -0.803 -0.571      -0.604 -0.333 -0.44  -0.4859  -0.4859  -0.0052   0      0      1     0      0      1      0        0           0.476 0.397 0.56  -0.18  423 0.223     0.098 0.148    0.294    0.071
    0.02   3.762 4.132796298  3.338796298  3.536       2.636899908  2.636899908 5.066125851  3.935125851  4.694671414 4.827671414  2.698846279  2.698846279 10.099  9.587    10.086           9.933           9.771     10.306     9.403      10.152      10.273    -1.593 -2.566  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.227 -0.021 1.128 1.884 -0.05   0.415  0.2854 0.0298 67 1225 -0.593 -0.458 -0.478 -0.785 -0.575      -0.593 -0.345 -0.458 -0.4859  -0.4859  -0.00518  0      0      1     0      0      1      0        0           0.482 0.401 0.563 -0.181 423 0.227     0.105 0.149    0.294    0.073
    0.025  3.859 4.246796298  3.392796298  3.633       2.731899908  2.731899908 5.140125851  4.094125851  4.779671414 4.911671414  2.800846279  2.800846279 10.181  9.667    10.172          10.009           9.85      10.387     9.481      10.292      10.329    -1.607 -2.578  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.221 -0.021 1.128 1.884 -0.05   0.43   0.2891 0.0302 67 1200 -0.569 -0.454 -0.464 -0.745 -0.573      -0.579 -0.362 -0.459 -0.4859  -0.4859  -0.00515  0      0      1     0      0      1      0        0           0.49  0.405 0.575 -0.183 423 0.231     0.12  0.15     0.31     0.076
    0.03   4.014 4.386796298  3.535796298  3.788       2.890899908  2.890899908 5.317125851  4.278125851  4.935671414 5.066671414  2.926846279  2.926846279 10.311  9.808    10.302          10.133           9.993     10.498     9.592      10.459      10.451    -1.63  -2.594  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.215 -0.021 1.128 1.884 -0.05   0.445  0.2932 0.0306 67 1200 -0.539 -0.455 -0.446 -0.69  -0.565      -0.561 -0.38  -0.464 -0.4908  -0.4908  -0.00511  0      0      1     0      0      1      0        0           0.5   0.413 0.589 -0.188 423 0.239     0.145 0.153    0.313    0.077
    0.04   4.223 4.553796298  3.747796298  3.997       3.075899908  3.075899908 5.564125851  4.531125851  5.182671414 5.312671414  3.069846279  3.069846279 10.588 10.086    10.602          10.404          10.317     10.744     9.834      10.818      10.678    -1.657 -2.629  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.207 -0.021 1.128 1.884 -0.05   0.46   0.3004 0.0313 67 1200 -0.468 -0.453 -0.431 -0.636 -0.546      -0.508 -0.403 -0.466 -0.49569 -0.49569 -0.00505  0      0      1     0      0      1      0        0           0.515 0.439 0.616 -0.205 423 0.261     0.177 0.159    0.322    0.08
    0.05   4.456 4.745796298  3.959796298  4.23        3.287899908  3.287899908 5.843125851  4.816125851  5.457671414 5.586671414  3.236846279  3.236846279 10.824 10.379    10.862          10.634          10.563     10.981    10.027      11.102      10.86     -1.687 -2.649  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.201 -0.021 1.128 1.884 -0.05   0.475  0.3048 0.0316 67 1225 -0.403 -0.452 -0.42  -0.594 -0.519      -0.461 -0.427 -0.468 -0.49823 -0.49823 -0.00497  0      0      1     0.1   -0.1   -0.063 -0.05     0           0.528 0.473 0.653 -0.23  423 0.285     0.2   0.167    0.33     0.077
    0.075  4.742 4.972796298  4.231796298  4.516       3.560899908  3.560899908 6.146125851  5.126125851  5.788671414 5.917671414  3.446846279  3.446846279 11.084 10.65     11.184          10.888          10.785     11.25     10.265      11.424      11.093    -1.715 -2.65   0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.19  -0.021 1.128 1.884 -0.05   0.49   0.2992 0.0321 67 1350 -0.325 -0.456 -0.442 -0.586 -0.497      -0.452 -0.458 -0.473 -0.49724 -0.49724 -0.00489  0.05  -0.043 -0.025 0.3   -0.34  -0.2   -0.075    0.078       0.53  0.529 0.722 -0.262 423 0.339     0.205 0.184    0.299    0.063
    0.1    4.952 5.160796298  4.471796298  4.726       3.788899908  3.788899908 6.346125851  5.333125851  5.998671414 6.126671414  3.643846279  3.643846279 11.232 10.816    11.304          11.03           10.841     11.466    10.467      11.49       11.283    -1.737 -2.647  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.182 -0.021 1.128 1.884 -0.05   0.505  0.2854 0.032  67 1450 -0.264 -0.468 -0.485 -0.629 -0.486      -0.498 -0.49  -0.482 -0.49471 -0.49471 -0.00478  0.1   -0.085 -0.05  0.333 -0.377 -0.222 -0.081    0.075       0.524 0.517 0.712 -0.239 423 0.347     0.185 0.176    0.31     0.061
    0.15   5.08  5.285796298  4.665796298  4.848       3.945899908  3.945899908 6.425125851  5.420125851  6.103671414 6.230671414  3.798846279  3.798846279 11.311 10.883    11.402          11.103          10.809     11.619    10.566      11.32       11.503    -1.745 -2.634  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.171 -0.021 1.162 1.884 -0.06   0.52   0.2814 0.0325 67 1500 -0.25  -0.484 -0.546 -0.729 -0.499      -0.568 -0.536 -0.499 -0.48583 -0.48583 -0.0046   0.164 -0.139 -0.082 0.29  -0.29  -0.193 -0.091    0.064       0.51  0.457 0.644 -0.185 423 0.313     0.123 0.164    0.307    0.076
    0.2    5.035 5.277796298  4.661796298  4.798       3.943899908  3.943899908 6.288125851  5.289125851  6.013671414 6.140671414  3.827846279  3.827846279 11.055 10.633    11.183          10.841          10.519     11.351    10.33       10.927      11.32     -1.732 -2.583  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.163 -0.021 1.187 1.884 -0.068  0.535  0.291  0.0306 67 1425 -0.288 -0.498 -0.612 -0.867 -0.533      -0.667 -0.584 -0.522 -0.47383 -0.47383 -0.00434  0.164 -0.139 -0.082 0.177 -0.192 -0.148 -0.092    0.075       0.501 0.432 0.64  -0.138 423 0.277     0.11  0.163    0.301    0.07
    0.25   4.859 5.154796298  4.503796298  4.618       3.800899908  3.800899908 5.972125851  4.979125851  5.849671414 5.974671414  3.765846279  3.765846279 10.803 10.322    10.965          10.583          10.268     11.063    10.124      10.555      11.147    -1.696 -2.539  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.156 -0.021 1.204 1.884 -0.075  0.55   0.2758 0.0306 67 1350 -0.36  -0.511 -0.688 -1.011 -0.592      -0.781 -0.654 -0.555 -0.47696 -0.47696 -0.00402  0.08  -0.08  -0.053 0.1   -0.035 -0.054  0        0           0.492 0.45  0.633 -0.185 423 0.26      0.119 0.169    0.233    0.077
    0.3    4.583 4.910796298  4.276796298  4.34        3.491899908  3.491899908 5.582125851  4.592125851  5.603671414 5.728671414  3.602846279  3.602846279 10.669 10.116    10.87           10.443          10.134     10.878    10.077      10.328      11.079    -1.643 -2.528  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.151 -0.021 1.215 1.884 -0.082  0.565  0.2719 0.0323 67 1250 -0.455 -0.514 -0.748 -1.133 -0.681      -0.867 -0.725 -0.596 -0.4845  -0.4845  -0.0037   0      0      1     0      0      1      0        0           0.492 0.436 0.584 -0.158 423 0.254     0.092 0.159    0.22     0.065
    0.4    4.18  4.548796298  3.919796298  3.935       3.128899908  3.128899908 5.091125851  4.089125851  5.151671414 5.277671414  3.343846279  3.343846279 10.116  9.561    10.411           9.884           9.598     10.296     9.539       9.639      10.547    -1.58  -2.452  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.143 -0.022 1.227 1.884 -0.091  0.58   0.2539 0.0302 67 1150 -0.617 -0.51  -0.802 -1.238 -0.772      -0.947 -0.801 -0.643 -0.48105 -0.48105 -0.00342 -0.13   0.113  0.087 0      0.05   0.2    0        0           0.492 0.433 0.556 -0.19  423 0.23      0.044 0.158    0.222    0.064
    0.5    3.752 4.168796298  3.486796298  3.505       2.640899908  2.640899908 4.680125851  3.571125851  4.719671414 4.848671414  3.028846279  3.028846279  9.579  8.973     9.901           9.341           9.097      9.711     9.03        9.03       10.049    -1.519 -2.384  0.1 -0.00657  -0.00541  -0.00387  -0.00862  -0.00397  -0.00787  -0.00255  -0.00219  -0.00401        -0.00217   -0.00311  -0.00217   -0.00355  1.143 -0.023 1.234 1.884 -0.1    0.595  0.2482 0.0295 67 1025 -0.757 -0.506 -0.845 -1.321 -0.838      -1.003 -0.863 -0.689 -0.46492 -0.46492 -0.00322 -0.2    0.176  0.118 0      0.1    0.2    0        0           0.492 0.428 0.51  -0.186 423 0.225     0.038 0.16     0.243    0.044
    0.75   3.085 3.510796298  2.710796298  2.837       1.987899908  1.987899908 3.906125851  2.844125851  3.995671414 4.129671414  2.499846279  2.499846279  8.837  8.246     9.335           8.593           8.324      8.934     8.258       8.258       9.327    -1.44  -2.338  0.1 -0.00635  -0.00478  -0.00342  -0.00763  -0.00351  -0.0068   -0.00211  -0.00189  -0.00347        -0.00188   -0.00269  -0.00188   -0.00307  1.217 -0.026 1.24  1.884 -0.115  0.61   0.2227 0.0266 67  900 -0.966 -0.5   -0.911 -1.383 -0.922      -1.052 -0.942 -0.745 -0.43439 -0.43439 -0.00312 -0.401  0.284  0.167 0      0.2    0.125 -0.2      0.012       0.492 0.448 0.471 -0.177 422 0.218     0.04  0.175    0.241    0.04
    1.0    2.644 3.067796298  2.238796298  2.396       1.553899908  1.553899908 3.481125851  2.371125851  3.512671414 3.653671414  2.140846279  2.140846279  8.067  7.507     8.68            7.817           7.557      8.164     7.467       7.417       8.504    -1.419 -2.267  0.1 -0.0058   -0.00415  -0.00297  -0.00663  -0.00305  -0.00605  -0.00187  -0.00168  -0.00309        -0.00167   -0.00239  -0.00167   -0.00273  1.27  -0.028 1.24  1.884 -0.134  0.625  0.1969 0.0231 67  800 -0.986 -0.49  -0.926 -1.414 -0.932      -1.028 -0.96  -0.777 -0.38484 -0.38484 -0.0031  -0.488  0.346  0.203 0      0.245  0.153 -0.245    0.037       0.492 0.43  0.43  -0.166 422 0.227     0.015 0.195    0.195    0.043
    1.5    2.046 2.513796298  1.451796298  1.799       0.990899908  0.990899908 2.870125851  1.779125851  2.875671414 3.023671414  1.645846279  1.645846279  6.829  6.213     7.581           6.573           6.35       6.896     6.22        6.18        7.204    -1.4   -2.166  0.1 -0.00505  -0.00342  -0.00245  -0.00546  -0.00252  -0.00498  -0.00154  -0.00139  -0.00254        -0.00138   -0.00197  -0.00138   -0.00225  1.344 -0.031 1.237 1.884 -0.154  0.64   0.1452 0.0118 67  760 -0.966 -0.486 -0.888 -1.43  -0.814      -0.971 -0.942 -0.79  -0.32318 -0.32318 -0.0031  -0.578  0.48   0.24  0      0.32   0.2   -0.32     0.064       0.492 0.406 0.406 -0.111 422 0.244    -0.047 0.204    0.204   -0.034
    2.0    1.556 2.061796298  0.906796298  1.31        0.534899908  0.534899908 2.507125851  1.293125851  2.327671414 2.481671414  1.217846279  1.217846279  5.871  5.206     6.671           5.609           5.434      5.935     5.261       5.161       6.227    -1.391 -2.077  0.1 -0.00429  -0.0029   -0.00208  -0.00463  -0.00214  -0.00423  -0.00131  -0.00118  -0.00216        -0.00117   -0.00167  -0.00117   -0.00191  1.396 -0.034 1.232 1.884 -0.154  0.655  0.06   0.007  67  760 -0.901 -0.475 -0.808 -1.421 -0.725      -0.901 -0.891 -0.765 -0.26577 -0.26577 -0.0031  -0.645  0.579  0.254 0      0.37   0.239 -0.28     0.14        0.492 0.393 0.393  0     422 0.231    -0.036 0.196    0.196   -0.036
    2.5    1.167 1.709796298  0.392796298  0.922       0.186899908  0.186899908 2.160125851  0.895125851  1.950671414 2.111671414  0.871846279  0.871846279  5.2    4.594     6.047           4.932           4.773      5.234     4.567       4.517       5.517    -1.394 -2.015  0.1 -0.00369  -0.0025   -0.00179  -0.00399  -0.00184  -0.00364  -0.00113  -0.00101  -0.00186        -0.00101   -0.00144  -0.00101   -0.00164  1.437 -0.036 1.227 1.884 -0.154  0.67   0      0       0  760 -0.822 -0.453 -0.743 -1.391 -0.632      -0.822 -0.842 -0.724 -0.21236 -0.21236 -0.0031  -0.678  0.609  0.267 0      0.4    0.264 -0.313    0.19        0.492 0.381 0.381  0     421 0.222    -0.025 0.169    0.169   -0.029
    3.0    0.92  1.456796298  0.099796298  0.675      -0.087100092 -0.087100092 1.969125851  0.607125851  1.766671414 1.932671414  0.596846279  0.596846279  4.83   4.206     5.667           4.556           4.441      4.849     4.176       4.076       5.157    -1.416 -2.012  0.1 -0.00321  -0.00217  -0.00156  -0.00347  -0.0016   -0.00316  -0.000979 -0.00088  -0.00161        -0.000873  -0.00125  -0.000873  -0.00143  1.47  -0.038 1.223 1.949 -0.154  0.685  0      0       0  760 -0.751 -0.428 -0.669 -1.343 -0.57       -0.751 -0.787 -0.675  0       -0.17807 -0.0031  -0.772  0.635  0.265 0      0.43   0.287 -0.355    0.165       0.492 0.367 0.367  0     419 0.199    -0.03  0.177    0.177   -0.011
    4.0    0.595 1.207796298 -0.356203702  0.352      -0.353100092 -0.353100092 1.675125851  0.303125851  1.524671414 1.698671414  0.268846279  0.268846279  4.173  3.517     4.97            3.893           3.849      4.074     3.495       3.445       4.55     -1.452 -1.989  0.1 -0.00244  -0.00165  -0.00118  -0.00264  -0.00122  -0.00241  -0.000745 -0.00067  -0.00123        -0.000664  -0.000952 -0.000664  -0.00109  1.523 -0.044 1.216 2.031 -0.154  0.7    0      0       0  760 -0.68  -0.396 -0.585 -1.297 -0.489      -0.68  -0.706 -0.613  0       -0.13729 -0.0031  -0.699  0.709  0.259 0      0.44   0.303 -0.417    0.163       0.492 0.33  0.33   0     416 0.191    -0.042 0.158    0.158    0.033
    5.0    0.465 1.131796298 -0.601203702  0.223      -0.491100092 -0.491100092 1.601125851  0.183125851  1.483671414 1.665671414  0.014846279  0.014846279  3.833  3.142     4.592           3.547           3.502      3.814     3.038       3.038       4.229    -1.504 -1.998  0.1 -0.0016   -0.00125  -0.000895 -0.002    -0.000919 -0.00182  -0.000564 -0.000507 -0.000929       -0.000503  -0.00072  -0.000503  -0.000822 1.564 -0.048 1.21  2.131 -0.154  0.715  0      0       0  760 -0.592 -0.353 -0.506 -1.233 -0.421      -0.592 -0.621 -0.536  0       -0.07733 -0.0031  -0.642  0.63   0.215 0      0.45   0.321 -0.45     0.132       0.492 0.298 0.298  0     415 0.181     0.005 0.132    0.132    0.014                                                                    
    7.5    0.078 0.758796298 -1.137203702 -0.162      -0.837100092 -0.837100092 1.270125851 -0.143874149  1.175671414 1.366671414 -0.446153721 -0.446153721  3.132  2.391     3.65            2.84            2.821      3.152     2.368       2.368       3.554    -1.569 -2.019  0.1 -0.000766 -0.000519 -0.000371 -0.000828 -0.000382 -0.000755 -0.000234 -0.00021  -0.000385       -0.000209  -0.000299 -0.000209  -0.000341 1.638 -0.059 1.2   2.185 -0.154  0.73   0      0       0  760 -0.494 -0.311 -0.418 -1.147 -0.357      -0.52  -0.52  -0.444  0       -0.05443 -0.0031  -0.524  0.306  0.175 0      0.406  0.312 -0.35     0.15        0.492 0.254 0.254  0     419 0.181    -0.016 0.113    0.113    0.016
    10.0   0.046 0.708796298 -1.290203702 -0.193      -0.864100092 -0.864100092 1.364125851 -0.195874149  1.271671414 1.462671414 -0.473153721 -0.473153721  2.72   2.031     2.95            2.422           2.408      2.791     1.939       1.939       3.166    -1.676 -2.047  0.1  0         0         0         0         0         0         0         0         0               0          0         0          0        1.69  -0.067 1.194 2.35  -0.154  0.745  0      0       0  760 -0.395 -0.261 -0.321 -1.06  -0.302      -0.395 -0.42  -0.352  0       -0.03313 -0.0031  -0.327  0.182  0.121 0      0.345  0.265 -0.331    0.117       0.492 0.231 0.231  0     427 0.181     0.04  0.11     0.11     0.017
    """)

    CONSTANTS = {"b4": 0.1, "f3": 0.05, "Vb": 200, "Vref_Fnl": 760, "V1": 270, "Vref": 760}
}


class ParkerEtAl2020SSlab(ParkerEtAl2020SInter):
    """
    Modifications for subduction slab.
    """

    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.SUBDUCTION_INTRASLAB

    # slab also requires hypo_depth
    REQUIRES_RUPTURE_PARAMETERS = {'mag', 'hypo_depth'}

    def _c0(self, C, C_PGA):
        if self.saturation_region is None:
            c0_col = "c0slab"
        elif self.region == "SA":
            c0_col = self.saturation_region + "_c0slab"
        else:
            # no more specific region available
            c0_col = self.region + "_c0slab"
        return C[c0_col], C_PGA[c0_col]

    def _get_mb(self):
        mb_regions = ("Aleutian", "AK", "Cascadia", "CAM_S", "CAM_N", \
            "JP_Pac", "JP_Phi", "SA_N", "SA_S", "TW_W", "TW_E")
        if self.saturation_region in mb_regions:
            i = mb_regions.index(self.saturation_region)
            Mb = (7.98, 7.2, 7.2, 7.6, 7.4, 7.65, 7.55, 7.3, 7.25, 7.7, 7.7)[i]
        else:
            Mb = 7.6

        return Mb

    def _path_term_h(self, mag, Mb):
        if mag <= Mb:
            m = (math.log10(35) - math.log10(3.12)) / (Mb - 4)
            return 10 ** (m * (mag - Mb) + math.log10(35))
        else:
            return 35

    def _a0(self, C, C_PGA):
        # isolate regional anelastic coefficient, a0
        if self.region is None:
            return C["a0"], C_PGA["a0"]
        else:
            return C[self.region + "_a0"], C_PGA[self.region + "_a0"]

    def _depth_scaling(self, C, hypo_depth):
        if hypo_depth >= C["db"]:
            return C["d"]
        elif hypo_depth <= 20:
            return C["m"] * (20 - C["db"]) + C["d"]
        else:
            return C["m"] * (hypo_depth - C["db"]) + C["d"]


class ParkerEtAl2020SInterAleutian(ParkerEtAl2020SInter):
    """
    For the Aleutian region.
    """
    def __init__():
        super(ParkerEtAl2020SInterAleutian, self).__init__(region="Aleutian")


class ParkerEtAl2020SInterAlaska(ParkerEtAl2020SInter):
    """
    For the Alaska region.
    """
    def __init__():
        super(ParkerEtAl2020SInterAlaska, self).__init__(region="AK")


class ParkerEtAl2020SInterCAMN(ParkerEtAl2020SInter):
    """
    For the CAM North region.
    """
    def __init__():
        super(ParkerEtAl2020SInterCAMN, self).__init__(region="CAM", \
            saturation_region="CAM_N")


class ParkerEtAl2020SInterCAMS(ParkerEtAl2020SInter):
    """
    For the CAM South region.
    """
    def __init__():
        super(ParkerEtAl2020SInterCAMS, self).__init__(region="CAM", \
            saturation_region="CAM_S")


class ParkerEtAl2020SInterCascadia(ParkerEtAl2020SInter):
    """
    Cascadia, other mapped basin (Tacoma, Everett, Georgia, etc.).
    """
    def __init__():
        super(ParkerEtAl2020SInterCascadia, self).__init__(region="Cascadia")


class ParkerEtAl2020SInterCascadiaOut(ParkerEtAl2020SInter):
    """
    Cascadia, estimate of Z2.5 outside mapped basin.
    """
    def __init__():
        super(ParkerEtAl2020SInterCascadiaOut, self).__init__( \
            region="Cascadia", basin="out")


class ParkerEtAl2020SInterCascadiaSeattle(ParkerEtAl2020SInter):
    """
    Cascadia, Seattle basin.
    """
    def __init__():
        super(ParkerEtAl2020SInterCascadiaSeattle, self).__init__( \
            region="Cascadia", basin="Seattle")


class ParkerEtAl2020SInterJapanPac(ParkerEtAl2020SInter):
    """
    For the Japan Pac region.
    """
    def __init__():
        super(ParkerEtAl2020SInterJapanPac, self).__init__(region="JP", \
            saturation_region="JP_Pac")


class ParkerEtAl2020SInterJapanPhi(ParkerEtAl2020SInter):
    """
    For the Japan Phi region.
    """
    def __init__():
        super(ParkerEtAl2020SInterJapanPhi, self).__init__(region="JP", \
            saturation_region="JP_Phi")


class ParkerEtAl2020SInterSAN(ParkerEtAl2020SInter):
    """
    For the SA North region.
    """
    def __init__():
        super(ParkerEtAl2020SInterSAN, self).__init__(region="SA", \
            saturation_region="SA_N")


class ParkerEtAl2020SInterSAS(ParkerEtAl2020SInter):
    """
    For the SA South region.
    """
    def __init__():
        super(ParkerEtAl2020SInterSAS, self).__init__(region="SA", \
            saturation_region="SA_S")


class ParkerEtAl2020SInterTaiwanE(ParkerEtAl2020SInter):
    """
    For the Taiwan East region.
    """
    def __init__():
        super(ParkerEtAl2020SInterTaiwanE, self).__init__(region="TW", \
            saturation_region="TW_E")


class ParkerEtAl2020SInterTaiwanW(ParkerEtAl2020SInter):
    """
    For the Taiwan West region.
    """
    def __init__():
        super(ParkerEtAl2020SInterTaiwanW, self).__init__(region="TW", \
            saturation_region="TW_W")


class ParkerEtAl2020SSlabAleutian(ParkerEtAl2020SSlab):
    """
    For the Aleutian region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabAleutian, self).__init__(region="Aleutian")


class ParkerEtAl2020SSlabAlaska(ParkerEtAl2020SSlab):
    """
    For the Alaska region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabAlaska, self).__init__(region="AK")


class ParkerEtAl2020SSlabCAMN(ParkerEtAl2020SSlab):
    """
    For the CAM North region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabCAMN, self).__init__(region="CAM", \
            saturation_region="CAM_N")


class ParkerEtAl2020SSlabCAMS(ParkerEtAl2020SSlab):
    """
    For the CAM South region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabCAMS, self).__init__(region="CAM", \
            saturation_region="CAM_S")


class ParkerEtAl2020SSlabCascadia(ParkerEtAl2020SSlab):
    """
    Cascadia, other mapped basin (Tacoma, Everett, Georgia, etc.).
    """
    def __init__():
        super(ParkerEtAl2020SSlabCascadia, self).__init__(region="Cascadia")


class ParkerEtAl2020SSlabCascadiaOut(ParkerEtAl2020SSlab):
    """
    Cascadia, estimate of Z2.5 outside mapped basin.
    """
    def __init__():
        super(ParkerEtAl2020SSlabCascadiaOut, self).__init__( \
            region="Cascadia", basin="out")


class ParkerEtAl2020SSlabCascadiaSeattle(ParkerEtAl2020SSlab):
    """
    Cascadia, Seattle basin.
    """
    def __init__():
        super(ParkerEtAl2020SSlabCascadiaSeattle, self).__init__( \
            region="Cascadia", basin="Seattle")


class ParkerEtAl2020SSlabJapanPac(ParkerEtAl2020SSlab):
    """
    For the Japan Pac region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabJapanPac, self).__init__(region="JP", \
            saturation_region="JP_Pac")


class ParkerEtAl2020SSlabJapanPhi(ParkerEtAl2020SSlab):
    """
    For the Japan Phi region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabJapanPhi, self).__init__(region="JP", \
            saturation_region="JP_Phi")


class ParkerEtAl2020SSlabSAN(ParkerEtAl2020SSlab):
    """
    For the SA North region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabSAN, self).__init__(region="SA", \
            saturation_region="SA_N")


class ParkerEtAl2020SSlabSAS(ParkerEtAl2020SSlab):
    """
    For the SA South region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabSAS, self).__init__(region="SA", \
            saturation_region="SA_S")


class ParkerEtAl2020SSlabTaiwanE(ParkerEtAl2020SSlab):
    """
    For the Taiwan East region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabTaiwanE, self).__init__(region="TW", \
            saturation_region="TW_E")


class ParkerEtAl2020SSlabTaiwanW(ParkerEtAl2020SSlab):
    """
    For the Taiwan West region.
    """
    def __init__():
        super(ParkerEtAl2020SSlabTaiwanW, self).__init__(region="TW", \
            saturation_region="TW_W")


def Aleatory_Function(period, Rrup, VS30):
    """
    Generate tau, phi, and total sigma computed from both
    total and partitioned phi models.
    """

    # coefficients
    coeff = pd.read_csv("Table_E3_Aleatory_Coefficients.csv", index_col=0)
    if period == -1: # PGV
        coeff = coeff.loc[-1]
    elif period == 0: # PGA
        coeff = coeff.loc[0]
    else:
        coeff = coeff.loc[period]

    # define period-independent coefficients for phi models
    V1 = 200
    V2 = 500
    R1 = 200
    R2 = 500
    R3 = 200
    R4 = 500
    R5 = 500
    R6 = 800

    # total Phi
    PhiRV = np.zeros(len(VS30))

    for i in range(len(VS30)):
        if Rrup[i] <= R1:
            PhiRV[i] = coeff["ɸ21"]
        elif Rrup[i] >= R2:
            PhiRV[i] = coeff["ɸ22"]
        else:
            PhiRV[i] = ((coeff["ɸ22"] - coeff["ɸ21"]) \
                / (math.log(R2) - math.log(R1))) \
                * (math.log(Rrup[i]) - math.log(R1)) + coeff["ɸ21"]

        if VS30[i] <= V1:
            PhiRV[i] += coeff["ɸ2V"] * (math.log(R2 / max(R1, min(R2, Rrup[i]))) \
                / math.log(R2 / R1))
        elif VS30[i] < V2:
            PhiRV += coeff["ɸ2V"] * ((math.log(V2 / min(V2, VS30[i]))) \
                / (math.log(V2 / V1))) \
                * (math.log(R2 / max(R1, min(R2, Rrup[i]))) \
                / (math.log(R2 / R1)))

    Phi_tot = np.sqrt(PhiRV)  

    # partitioned Phi
    PhiS2SV = np.repeat(coeff["ɸ2S2S,0"], len(VS30))
    PhiSSR = np.zeros_like(PhiRV)
    PhiSSV = np.repeat(coeff.a2, len(VS30))

    for i in range(len(VS30)):
        if VS30[i] <= V1:
            PhiS2SV[i] += (coeff.a1 * math.log(V1 / coeff.VM)) \
                * (math.log(R4 / max(R3, min(R4, Rrup[i]))) / math.log(R4 / R3))
            PhiSSV[i] *= math.log(V1 / coeff.VM) \
                * (math.log(R4 / max(R3, min(R4, Rrup[i]))) / math.log(R4 / R3))
        elif VS30[i] >= V2:
            PhiS2SV[i] += (coeff.a1 * math.log(V2 / coeff.VM))
            PhiSSV[i] *= math.log(V2 / coeff.VM)
        elif VS30[i] > V1 and VS30[i] < coeff.VM:
            PhiS2SV[i] += (coeff["a1"] * math.log(VS30[i] / coeff.VM)) \
                * (math.log(R4 / max(R3, min(R4, Rrup[i]))) / math.log(R4 / R3))
            PhiSSV[i] *= math.log(VS30[i] / coeff.VM) \
                * (math.log(R4 / max(R3, min(R4, Rrup[i]))) / math.log(R4 / R3))
        elif VS30[i] >= coeff.VM and VS30[i] < V2:
            PhiS2SV[i] += (coeff.a1 * math.log(VS30[i] / coeff.VM))
            PhiSSV[i] *= math.log(VS30[i] / coeff.VM)

        if Rrup[i] <= R5:
            PhiSSR[i] = coeff["ɸ2SS,1"]
        elif Rrup[i] >= R6:
            PhiSSR[i] = coeff["ɸ2SS,2"]
        else:
            PhiSSR[i] = ((coeff["ɸ2SS,2"] - coeff["ɸ2SS,1"]) \
                / (math.log(R6) - math.log(R5))) \
                * (math.log(Rrup[i]) - math.log(R5)) + coeff["ɸ2SS,1"]

    PhiC = np.sqrt(PhiS2SV + PhiSSR + PhiSSV)

    # define output matrix
    return {"Tau": coeff.Tau,
            "Phi_total": Phi_tot,
            "Phi_SS": np.sqrt(PhiSSR + PhiSSV),
            "PhiS2S": np.sqrt(PhiS2SV),
            "Phi_partitioned": PhiC,
            "Sigma_total": np.sqrt(coeff.Tau ** 2 + Phi_tot ** 2),
            "Sigma_partitioned": np.sqrt(coeff.Tau ** 2 + PhiC ** 2)
        }
