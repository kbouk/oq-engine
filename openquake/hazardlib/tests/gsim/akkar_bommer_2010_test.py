# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2012-2021 GEM Foundation
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

from openquake.hazardlib.gsim.akkar_bommer_2010 import AkkarBommer2010
from openquake.hazardlib.tests.gsim.utils import BaseGSIMTestCase


class AkkarBommer2010TestCase(BaseGSIMTestCase):
    GSIM_CLASS = AkkarBommer2010

    # Test data were obtained from a tool given by the authors
    # The data of the values of the mean PGA and SA are in m/s2.

    def test_mean(self):
        self.check('AKBO10/AK10_MEAN.csv',
                    max_discrep_percentage=0.6)

    def test_std_intra(self):
        self.check('AKBO10/AK10_STD_INTRA.csv',
                    max_discrep_percentage=0.1)

    def test_std_inter(self):
        self.check('AKBO10/AK10_STD_INTER.csv',
                    max_discrep_percentage=0.1)

    def test_std_total(self):
        self.check('AKBO10/AK10_STD_TOTAL.csv',
                    max_discrep_percentage=0.1)
