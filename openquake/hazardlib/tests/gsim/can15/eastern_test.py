#
# Copyright (C) 2014-2018 GEM Foundation
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

from openquake.hazardlib.tests.gsim.utils import BaseGSIMTestCase
from openquake.hazardlib.gsim.can15.eastern import (EasternCan15Mid,
                                                    EasternCan15Upp,
                                                    EasternCan15Low)


class EasternCan15MidTestCase(BaseGSIMTestCase):
    GSIM_CLASS = EasternCan15Mid

    def test_mean(self):
        self.check('CAN15/GMPEt_ENA_med.csv',
                   max_discrep_percentage=0.4)
    """
    def test_std_total(self):
        self.check('SILVA02/SILVA02MblgAB1987NSHMP_STD_TOTAL.csv',
                   max_discrep_percentage=0.1)
    """
