# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2014-2020 GEM Foundation
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
Module exports :class:`CauzziEtAl2014Eurocode8scaled`,
"""
import numpy as np
# standard acceleration of gravity in m/s**2
from scipy.constants import g

from openquake.hazardlib.gsim.base import CoeffsTable, GMPE
from openquake.hazardlib import const
from openquake.hazardlib.imt import PGA, PGV, SA


class CauzziEtAl2014Eurocode8scaled(GMPE):
    """
    Implements GMPE developed by Carlo Cauzzi et al (2014) and published
    as C.Cauzzi, E. Faccioli, M. Vanini and A. Bianchini (2014) "Updated
    predictive equations for broadband (0.0 - 10.0 s) horizontal response
    spectra and peak ground motions, based on a global dataset of digital
    acceleration records", Bulletin of Earthquake Engineering, In Press

    Spectral acceleration (SA) values are obtained from displacement response
    spectrum  (DSR) values (as provided by the original equations) using the
    following formula ::

        SA = DSR * (2 * π / T) ** 2
    
    """
    #: Supported tectonic region type is active shallow crust,
    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.ACTIVE_SHALLOW_CRUST

    #: Supported intensity measure types are spectral acceleration, peak
    #: ground acceleration and peak ground velocity.
    #: The original paper provides coefficients for PGA and PGV, while SA
    #: is obtained from displacement response spectrum values.
    #: Coefficients for PGA are taken from the SA (0.01 s) spectral
    #: acceleration, as indicated in Page 11 (at the time of writing)
    #: of Cauzzi et al. (2014)
    DEFINED_FOR_INTENSITY_MEASURE_TYPES = set([
        PGA,
        PGV,
        SA
    ])

    #: Supported intensity measure component is the geometric mean of two
    #: horizontal components
    #: :attr:`~openquake.hazardlib.const.IMC.AVERAGE_HORIZONTAL`,
    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.AVERAGE_HORIZONTAL

    #: Supported standard deviation types are inter-event, intra-event and
    #: total
    DEFINED_FOR_STANDARD_DEVIATION_TYPES = set([
        const.StdDev.INTER_EVENT,
        const.StdDev.INTRA_EVENT,
        const.StdDev.TOTAL
    ])

    #: Required site parameter is only Vs30
    REQUIRES_SITES_PARAMETERS = {'vs30'}

    #: Required rupture parameters are magnitude and rake
    REQUIRES_RUPTURE_PARAMETERS = {'rake', 'mag'}

    #: Required distance measure is Rrup,
    REQUIRES_DISTANCES = {'rrup'}

    def get_mean_and_stddevs(self, sites, rup, dists, imt, stddev_types):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.get_mean_and_stddevs>`
        for spec of input and result values.
        """
        # extract dictionaries of coefficients specific to required
        # intensity measure type
        C = self.COEFFS[imt]

        mean = self._compute_mean(C, rup, dists, sites, imt)

        stddevs = self._get_stddevs(C, stddev_types, sites.vs30.shape[0])

        return mean, stddevs

    def _compute_mean(self, C, rup, dists, sites, imt):
        """
        Returns the mean ground motion acceleration and velocity
        """
        mean = (self._get_magnitude_scaling_term(C, rup.mag) +
                self._get_distance_scaling_term(C, rup.mag, dists.rrup) +
                self._get_style_of_faulting_term(C, rup.rake) +
                self._get_site_amplification_term(C, sites.vs30))
        # convert from cm/s**2 to g for SA and from cm/s**2 to g for PGA (PGV
        # is already in cm/s) and also convert from base 10 to base e.
        if imt.name == "PGA":
            mean = np.log((10 ** mean) * ((2 * np.pi / 0.01) ** 2) *
                          1e-2 / g)
        elif imt.name == "SA":
            mean = np.log((10 ** mean) * ((2 * np.pi / imt.period) ** 2) *
                          1e-2 / g)
        else:
            mean = np.log(10 ** mean)

        return mean

    def _get_magnitude_scaling_term(self, C, mag):
        """
        Returns the magnitude term
        """
        return C["c1"] + (C["m1"] * mag) + (C["m2"] * (mag ** 2.))

    def _get_distance_scaling_term(self, C, mag, rrup):
        """
        Returns the distance scaling parameter
        """
        return (C["r1"] + C["r2"] * mag) * np.log10(rrup + C["r3"])

    def _get_style_of_faulting_term(self, C, rake):
        """
        Returns the style of faulting term. Cauzzi et al. determind SOF from
        the plunge of the B-, T- and P-axes. For consistency with existing
        GMPEs the Wells & Coppersmith model is preferred
        """
        if rake > -150.0 and rake <= -30.0:
            return C['fN']
        elif rake > 30.0 and rake <= 150.0:
            return C['fR']
        else:
            return C['fSS']

    def _get_site_amplification_term(self, C, vs30):
        """
        Returns the site amplification term on the basis of Eurocode 8
        site class
        """
        s_b, s_c, s_d = self._get_site_dummy_variables(vs30)
        return (C["sB"] * s_b) + (C["sC"] * s_c) + (C["sD"] * s_d)

    def _get_site_dummy_variables(self, vs30):
        """
        Returns the Eurocode 8 site class dummy variable
        """
        s_b = np.zeros_like(vs30)
        s_c = np.zeros_like(vs30)
        s_d = np.zeros_like(vs30)
        s_b[np.logical_and(vs30 >= 360., vs30 < 800.)] = 1.0
        s_c[np.logical_and(vs30 >= 180., vs30 < 360.)] = 1.0
        s_d[vs30 < 180] = 1.0
        return s_b, s_c, s_d

    def _get_stddevs(self, C, stddev_types, num_sites):
        """
        Return total standard deviation.
        """
        stddevs = []
        for stddev_type in stddev_types:
            assert stddev_type in self.DEFINED_FOR_STANDARD_DEVIATION_TYPES
            if stddev_type == const.StdDev.TOTAL:
                stddevs.append(np.log(10.0 ** C['sM']) + np.zeros(num_sites))
            elif stddev_type == const.StdDev.INTRA_EVENT:
                stddevs.append(np.log(10.0 ** C['f']) + np.zeros(num_sites))
            elif stddev_type == const.StdDev.INTER_EVENT:
                stddevs.append(np.log(10.0 ** C["tM"]) + np.zeros(num_sites))
        return stddevs

    #: Coefficient table constructed from the electronic suplements of the

    #: original paper.
    COEFFS = CoeffsTable(sa_damping=5, table="""\
    imt                       c1                   m1                    m2                    r1                   r2                    r3                   sB                   sC                   sD                    bV                 bV800                       VA                    fN                    fR                   fSS                    f                    t                    s                   tM                   sM
    pgv       0.483292714   0.5482239378818140   -0.0319470258028777   -2.8457788432226700   0.2406737047414070   6.51696666287798000   0.1919277313361110   0.3706196443240230   0.4978018189249720   -0.6909580227999990   -0.7596804404000000     883.9565406477700000   -0.1433313027208760    0.0184633160924233    0.0049897699311183   0.2398935826956730   0.2213004346208430   0.3263783286033860   0.2149404298227920   0.3220998664588330
    pga      -2.153913989   0.5237450060972680   -0.0609447663010394   -3.8019035608295600   0.3550808121411740   11.6415555876916000   0.2106985279596590   0.2825106921224770   0.2828846140789600   -0.3100704816000000   -0.7024376883999990    2319.1859784562300000   -0.0241122431339601    0.0724633666482452   -0.0563165754085399   0.2589229720745850   0.2214506097241730   0.3407073201666570   0.2162221044760760   0.3373323345485870
    0.0500   -0.133056941   0.7038280147755070   -0.0875507720994941   -4.4155335972196800   0.4140306595178590   15.9634085011888000   0.1678531023791990   0.1863342553869610   0.1392855607298930   -0.1000000000000000   -0.5639501998999990   30552.3271673005000000   -0.0389955855635790    0.0960304396771990   -0.0706779148995298   0.2702569776994650   0.2423624069839720   0.3630129065395790   0.2337736891265200   0.3573359367920780
    0.1000    0.720631637   0.6701555114371590   -0.0842487133409999   -4.2989668796524600   0.3950150942756780   16.9499399186483000   0.1982256814552770   0.2004113577343430   0.1312995606293180   -0.1000000000000000   -0.5923724273999990   36597.5600451842000000   -0.0282989830364419    0.1005680531402610   -0.0799511338270659   0.2864871213393960   0.2433368095307030   0.3758825262843640   0.2343281863791130   0.3701142656330040
    0.1500    0.457351183   0.6331119438041180   -0.0719075361587948   -3.8697055665013900   0.3527209416036150   13.7553799942078000   0.2489114740764020   0.3018776519585660   0.2531944049628660   -0.2273218226000000   -0.7549461000999990    5440.3520640067600000   -0.0299967463616727    0.0962871690940792   -0.0762552422410023   0.2888548904585920   0.2369264158171150   0.3735923905191180   0.2282717557908330   0.3681645586333300
    0.2000   -0.041706067   0.6394154973768270   -0.0625617809919999   -3.4154331729506900   0.3010051287415760   11.4534631595437000   0.2821393446741870   0.4058929876762180   0.3690896542349010   -0.4384492105000000   -0.8944358918000000    1898.2857019816500000   -0.0036711341998802    0.0693398950336865   -0.0633905167734821   0.2932537473600140   0.2159716768759310   0.3641998428792800   0.2112464445303770   0.3614177924057090
    0.3000   -0.44693261   0.6651087078884250   -0.0560927957029996   -3.0938863341046000   0.2735167424921670    8.2935173490201800   0.2096502844403170   0.4001251672249500   0.4335528490826920   -0.6554113151999990   -0.8545657526000000     967.9255537188150000   -0.0179995073864090    0.0508746350031907   -0.0417662944939413   0.2955895319193470   0.1990806049250280   0.3563793745962490   0.1961542457250350   0.3547529555849480
    0.4000   -0.9682344   0.7477063980675440   -0.0562692503039990   -2.8852884017037800   0.2536783288165920    6.2119923952061800   0.1858234788604210   0.4107333337437640   0.5209946684961200   -0.8100884283999990   -0.8530330874999990     794.5532205269830000    0.0004098177393169    0.0403886753646120   -0.0384916849988285   0.2987789982376510   0.2068578206071190   0.3633992951757350   0.2051740007093480   0.3624434581489560
    0.5000   -1.314364459   0.8260335951960020   -0.0600971406249981   -2.7937608332104700   0.2483537730430820    5.2021129207912500   0.1912072326769610   0.4163804535941900   0.6163803445766500   -0.9166134093000000   -0.8761241065999990     747.1063408592170000    0.0086757291814616    0.0281315838618958   -0.0297855596041406   0.2988253255683690   0.2171380197001870   0.3693852931565640   0.2163378482566530   0.3689154913924880
    0.7500   -1.972769452   1.0612712694853100   -0.0761444939880500   -2.8411938303340100   0.2583666046875160    5.0513970104537200   0.1680957619203300   0.4032102189640850   0.7080554315362520   -1.0313556675000000   -0.8579717241000000     675.6979435204260000    0.0239285639574445    0.0074392636316948   -0.0161682493304947   0.2951575001067500   0.2297001913951280   0.3740055184034380   0.2294277631124650   0.3738382649703680
    1.0000   -2.432723783   1.2134822214871800   -0.0854280000001306   -2.8543804213112900   0.2593699405690310    4.9780849514747200   0.1576721986608320   0.3903326170865970   0.6932630179184690   -0.9891875651000000   -0.8248044635000000     678.6122701764790000    0.0344742509193550   -0.0054363568289916   -0.0082972422158440   0.2963176996743180   0.2307500744544380   0.3755659409491340   0.2302608656402460   0.3752655664801600
    2.0000   -3.428939783   1.6562992065143400   -0.1154147661327820   -3.0442154569996200   0.2641813503629670    8.9746507855722500   0.1058745154124260   0.3256670883462820   0.5351158123025720   -0.7909590998000000   -0.6342277109999990     641.1223369683100000   -0.0162396506874878   -0.0019971914576055    0.0080969196977610   0.2906422190364900   0.2257008081025670   0.3679860789005580   0.2255881657370820   0.3679170015194690
    3.0000   -3.663741045   1.7276931468404900   -0.1155813789892250   -2.9923117217806700   0.2523813577739830   11.8386025178292000   0.1081958140488820   0.2968493026283440   0.4983702292088530   -0.7127096177999990   -0.5547507065000000     643.3004613025160000   -0.0434663752687055    0.0115341667660334    0.0062500594261708   0.2812581479022440   0.2324512752973370   0.3648831883613700   0.2315528559466120   0.3643115025063480
    4.0000   -3.529301652   1.6890940080884600   -0.1128841877050190   -3.1224660460706600   0.2822792909686670   12.7543160967594000   0.1119890714433590   0.2817361688665730   0.4534378584333170   -0.6428214690000000   -0.4939849281000000     651.4850608555060000   -0.0583039796710700    0.0092717900996661    0.0145442858770594   0.2713069027359440   0.2407315750359230   0.3627108031082710   0.2392999325376520   0.3617622053016260
    """)

