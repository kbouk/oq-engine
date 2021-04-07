# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2020, GEM Foundation
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
Module :mod:`openquake.hazardlib.gsim.sgobba_2020` implements
:class:`~openquake.hazardlib.gsim.sgobba_2020.SgobbaEtAl2020`
"""

import os
import re
import copy
import numpy as np
import pandas as pd
from scipy.constants import g as gravity_acc
from scipy.spatial import cKDTree
from openquake.hazardlib.geo import Point, Polygon
from openquake.hazardlib import const
from openquake.hazardlib.geo.mesh import Mesh
from openquake.hazardlib.imt import PGA, SA
from openquake.hazardlib.gsim.base import GMPE, CoeffsTable

# From http://www.csgnetwork.com/degreelenllavcalc.html
LEN_1_DEG_LAT_AT_43pt5 = 111.10245
LEN_1_DEG_LON_AT_43pt5 = 80.87665

DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'sgobba_2020')

REGIONS = {'1': [[13.37, 42.13], [13.60, 42.24], [13.48, 42.51], [13.19, 42.36]],
           '4': [[13.26, 42.41], [13.43, 42.49], [13.27, 43.02], [12.96, 42.86]],
           '5': [[13.03, 42.90], [13.21, 42.99], [13.10, 43.13], [12.90, 43.06]]}


class SgobbaEtAl2020(GMPE):
    """
    Implements the GMM proposed by Sgobba et al. (2020).

    :param event_id:
        A string identifying an event amongst the ones comprised in the
        list available in the file `event.csv`
    :param directionality:
        A boolean
    :param cluster:
        If set to 'None' no cluster correction applied. If 0 the OQ Engine
        finds the corresponding cluster using the rupture epicentral
        location.  Otherwise, if an integer ID is provided, that
        corresponds to the cluster id (available cluster indexes are 1, 4
        and 5)
    """

    #: Supported tectonic region type is 'active shallow crust'
    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.ACTIVE_SHALLOW_CRUST

    #: Set of :mod:`intensity measure types <openquake.hazardlib.imt>`
    #: this GSIM can calculate. A set should contain classes from module
    #: :mod:`openquake.hazardlib.imt`.
    DEFINED_FOR_INTENSITY_MEASURE_TYPES = {PGA, SA}

    #: Supported intensity measure component is the geometric mean of two
    #: horizontal components
    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.AVERAGE_HORIZONTAL

    #: Supported standard deviation types are inter-event, intra-event
    #: and total
    DEFINED_FOR_STANDARD_DEVIATION_TYPES = {
        const.StdDev.TOTAL,
        const.StdDev.INTER_EVENT,
        const.StdDev.INTRA_EVENT
    }

    #: Required site parameter is not set
    REQUIRES_SITES_PARAMETERS = set()

    #: Required rupture parameters is magnitude
    REQUIRES_RUPTURE_PARAMETERS = {'mag'}

    #: Required distance measure is Rjb
    REQUIRES_DISTANCES = {'rjb'}

    def __init__(self, event_id=None, directionality=False, cluster=None,
                 site=False, **kwargs):

        super().__init__(event_id=event_id,
                         directionality=directionality,
                         cluster=cluster,
                         **kwargs)

        # Set general information
        self.event_id = event_id
        self.directionality = directionality
        self.cluster = cluster
        self.site = site

        # Reading between-event std
        self.be = 0.0
        self.be_std = 0.0

        # Load the table with the between event coefficients
        if event_id is not None:
            self.event_id = event_id
            fname = os.path.join(DATA_FOLDER, 'event.csv')

            # Create dataframe with events
            df = pd.read_csv(fname, sep=';', index_col='id',
                             dtype={'id': 'string'})
            self.df = df
            assert event_id in df.index.values

    def get_mean_and_stddevs(self, sites, rup, dists, imt, stddev_types):
        """
        Eq.1 - page 2
        """

        # Set the between event correction
        if self.event_id is not None:
            label = "dBe_{:s}".format(imt.__str__())
            self.be = self.df.loc[self.event_id][label]
            # TODO
            # self.be_std = self.df.loc[self.event_id]['be_std']

        # Get site indexes. They are used for the site correction and the
        # cluster (path) correction
        if self.cluster != 0 or self.event_id is not None:

            # Load the coordinates of the nodes grid
            fname = os.path.join(DATA_FOLDER, 'grid.csv')
            coo = np.fliplr(np.loadtxt(fname, delimiter=";"))

            # Create a spatial index
            kdt = cKDTree(coo)
            tmp = [[s.location.longitude, s.location.latitude] for s in sites]
            dsts, self.idxs = kdt.query(np.array(tmp))

        # Ergodic coeffs
        C = self.COEFFS[imt]

        # Site correction
        sc = 0
        if self.site:
            sc = self._get_site_correction(sites.vs30.shape, imt)

        # Get mean
        mean = (C['a'] + self._get_magnitude_term(C, rup.mag) +
                self._get_distance_term(C, rup.mag, dists) +
                sc +
                self._get_cluster_correction(C, sites, rup, imt) +
                self.be)

        # To natural logarithm and fraction of g
        mean = np.log(10.0**mean/(gravity_acc*100))
        #mean = np.log(10.0**mean)

        # Get stds
        stds = []

        return mean, stds

    def _get_site_correction(self, shape, imt):
        """
        Get site correction
        """
        correction = np.zeros_like(shape)

        # Cluster coefficients
        fname = os.path.join(DATA_FOLDER, "S_model.csv")
        data = np.loadtxt(fname, delimiter=",")

        # Compute the site coefficients
        correction = np.zeros(shape)
        per = 0
        if re.search('SA', imt.__str__()):
            per = imt.period

        for idx in np.unique(self.idxs):
            tmp = data[int(idx)]
            correction[self.idxs == idx] = np.interp(per, self.PERIODS,
                                                     tmp[0:6])
        return correction

    def _get_cluster_correction(self, C, sites, rup, imt):
        """
        Get cluster correction. The user can specify various options through
        the cluster parameter. The available options are:
        - self.cluster = None
            In this case the code finds the most appropriate correction using
            the rupture position
        - self.cluster = 0
            No cluster correction
        - self.cluser = 1 or 4 or 5
            The code uses the correction for the given cluster
        """
        shape = sites.vs30.shape
        correction = np.zeros_like(shape)
        cluster = copy.copy(self.cluster)

        # No cluster correction
        if cluster is None:
            cluster = 0
            midp = rup.surface.get_middle_point()
            mesh = Mesh(np.array([midp.longitude]), np.array([midp.latitude]))

            for key in self.REGIONS:
                coo = np.array(REGIONS[key])
                pnts = [Point(lo, la) for lo, la in zip(coo[:, 0], coo[:, 1])]
                poly = Polygon(pnts)
                within = poly.intersects(mesh)
                if all(within):
                    cluster = int(key)
                    break

        if cluster == 0:
            return correction
        else:
            # Cluster coefficients
            fname = 'P_model_cluster{:d}.csv'.format(cluster)
            fname = os.path.join(DATA_FOLDER, fname)
            data = np.loadtxt(fname, delimiter=",", skiprows=1)

            # Compute the coefficients
            correction = np.zeros(shape)
            per = 0
            if re.search('SA', imt.__str__()):
                per = imt.period

            # NOTE: Checked for a few cases that the correction coefficients
            #       are correct
            for idx in np.unique(self.idxs):
                tmp = data[int(idx)]
                correction[self.idxs == idx] = np.interp(per, self.PERIODS,
                                                         tmp[0:6])
            # Adding L2L correction
            label = "dL2L_cluster{:d}".format(cluster)
            correction += C[label]

        return correction

    def _get_magnitude_term(self, C, mag):
        """
        Eq.2 - page 3
        """
        if mag <= self.consts['Mh']:
            return C['b1']*(mag-self.consts['Mh'])
        else:
            return C['b2']*(mag-self.consts['Mh'])

    def _get_distance_term(self, C, mag, dists):
        """
        Eq.3 - page 3
        """
        term1 = C['c1']*(mag-C['mref']) + C['c2']
        tmp = np.sqrt(dists.rjb**2+self.consts['PseudoDepth']**2)
        term2 = np.log10(tmp/self.consts['Rref'])
        term3 = C['c3']*(tmp-self.consts['Rref'])
        return term1 * term2 + term3

    PERIODS = np.array([0, 0.2, 0.5, 1.0, 2.0])

    COEFFS = CoeffsTable(sa_damping=5., table="""\
IMT              a                b1                b2                c1                c2                c3                   mref             sigma             dL2L_cluster1     dL2L_cluster4         dL2L_cluster5        tau_ev
PGA              2.92178299969904 0.549352522898805 0.195787600661646 0.182324348626393 -1.56833817017883 -0.00277072348000775 3.81278167434967 0.373287155304596 0.154652625958199 -0.0144001959308384   -0.0141006684390188  -0.0814912207894038
0.2              3.23371734550753 0.718110435825521 0.330819511910566 0.101391376086178 -1.47499081134392 -0.00235944669544279 3.52085298608413 0.3757532971338 0.142257128473462   -0.0295313493684611   -0.0242995747709838  -0.0779761977475732
0.50251256281407 3.16050217205595 0.838494386998919 0.466787811642044 0.105723089676    -1.48056328666322  0                   4.87194107479204 0.336027704871346 0.118125529818761  0.00929098048437728  -0.00995372305434456 -0.00828100722167989
1                2.58227846237728 0.85911311807545  0.519131261495525 0.146088352194266 -1.28019118368202  0                   5.42555199253122 0.324958646112493 0.124229747688977  0.000737173026444824 -0.00123578210338215  0.000181351036566464
2                1.88792168738756 0.727248116061721 0.47362977053987  0.244695132922949 -1.19816952711971  0                   5.26896508895249 0.316058351128692 0.127711124129548  5.60984632803441e-15 -1.18288330352055e-14 9.31778101896791e-15

    """)

    consts = {'Mh': 5.0,
              'Rref': 1.0,
              'PseudoDepth': 6.0}

    REGIONS = {'1': [13.37, 42.13, 14.94, 41.10, 15.23, 42.32, 13.26, 42.41,
                     13.03, 42.90, 14.81, 41.80],
               '4': [13.19, 42.36, 14.83, 41.17, 15.13, 42.38, 12.96, 42.86,
                     12.90, 43.06, 14.73, 41.85],
               '5': [13.37, 42.13, 14.94, 41.10, 15.23, 42.32, 13.26, 42.41,
                     13.03, 42.90, 14.81, 41.80]}
