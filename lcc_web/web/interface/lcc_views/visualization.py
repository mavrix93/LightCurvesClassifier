import os

import numpy as np
import pandas as pd
from django.conf import settings
from django.shortcuts import render
from lcc.data_manager.package_reader import PackageReader
from lcc.stars_processing.tools.visualization import plotUnsupProbabSpace

from interface.helpers import getFields, load_test_stars
from interface.helpers import makeDesc
from interface.helpers import parse_combinations
from interface.helpers import parse_comp_stars
from interface.helpers import parse_stars


def stars(request):
    PAGE_TITLE = "Show light curves"
    PAGE_INFO = "Select dat files of light curves or fits of stars. Also you can use prepared sample - just don't select anything"

    if "sub" in request.POST:
        fi = request.FILES.getlist("my_file")
        try:
            if fi:
                sta = parse_stars(fi)
            else:
                sta = load_test_stars(os.path.join(settings.TEST_SAMPLE, "sample1"))[:5]

        except Exception as e:
            return render(request, 'interface/error_page.html', {"error_m": "Couldn't parse star files: {}".format(str(e))})
        lcs = []
        labels = []
        for st in sta:
            if st.lightCurve:
                lcs.append(
                    [st.lightCurve.time.tolist(), st.lightCurve.mag.tolist(), st.lightCurve.err.tolist()])
                labels.append(str(st.name))

    else:
        lcs, labels = [], []

    return render(request, "interface/browse.html", {"page_title": PAGE_TITLE,
                                                     "page_info": PAGE_INFO,
                                                     "lcs": lcs,
                                                     "labels": labels})


def unsup_clust(request):
    PAGE_TITLE = "Unsupervised clustering"
    PAGE_INFO1 = '''There are text input per every parameter of descriptors and deciders. You have to specify just one  <br>
    value.
    <br><br>

    For evaluating content as python code wrapp the code into "`". For example:<br><br>

    `True` - bool value (not string)<br>
    `7*6` - integer (42)<br>
    `[("b_mag","v_mag"),("r_mag","i_mag")]` - list of tuples of strings<br><br>

    It is possible to select multiple descriptors and deciders. <br>
    <br>
    NOTE that it raises error if loaded stars dont contain desired attribute (light curve, color index etc)
    '''

    PAGE_INFO2 = """After submiting you can aim courser to a point in probability plot to see additional<br>
information about the star. You can also click on it to see the light curve"""

    if "descriptors_l" in request.POST:
        sample_files = request.FILES.getlist("sample_files")

        descriptor_names = request.POST.get("descriptors_l", "").split(";")
        deciders_names = request.POST.get("deciders_l", "").split(";")

        tuned_params, _static_params = parse_combinations(
            descriptor_names + deciders_names, request.POST, split_by=":")
        static_params = parse_comp_stars(request.FILES)

        if not (tuned_params and hasattr(tuned_params, "__iter__") and tuned_params[0] == {}):
            return render(request, 'interface/error_page.html',
                          {
                              "error_m": "Parameters ranges are no supported.<br>Insert just exact values.<br>Got %i combinations" % len(
                                  tuned_params)})

        # if tuned_params[0:
        #    raise QueryInputError("Dont insert ranges, just exact values!")

        for key, value in _static_params.items():
            if key in static_params:
                static_params[key].update(value)
            else:
                static_params[key] = value

        try:
            if not sample_files:
                stars = load_test_stars(os.path.join(settings.TEST_SAMPLE, "sample1"))
            else:
                stars = parse_stars(sample_files)

        except Exception as e:
            return render(request, 'interface/error_page.html', {"error_m": "Couldn't parse star files<br><br>Error msg: %s" % str(e)})

        deciders = [desc for desc in PackageReader().getClasses(
            "unsup_deciders") if desc.__name__ in deciders_names]
        descriptors = [desc for desc in PackageReader().getClasses(
            "descriptors") if desc.__name__ in descriptor_names]

        ready_descriptors = makeDesc(descriptors, static_params)

        if deciders:
            act_decider = makeDesc(deciders, static_params)[0]


        lcs = []
        labels = []
        st_info = []
        for st in stars:
            lc = st.lightCurve
            if lc:
                lab = st.name
                labels.append(lab)

                stkeys = list(st.more.keys())
                stval = list(st.more.values())

                if len(stkeys) >= 3:
                    inf = lab + "<br>" + \
                          "\t|\t".join(stkeys[:3]) + "<br>" + \
                          "\t|\t".join([str(x) for x in stval[:3]])

                    inf += "<br>" + \
                           "\t|\t".join(stkeys[3:]) + "<br>" + \
                           "\t|\t".join([str(x) for x in stval[3:]])
                else:
                    inf = lab + "<br>" + \
                          "\t|\t".join(stkeys) + "<br>" + \
                          "\t|\t".join([str(x) for x in stval])

                st_info.append(str(inf))
                lcs.append([lc.time.tolist(), lc.mag.tolist()])

        coords = []
        for desc in ready_descriptors:
            c = desc.getSpaceCoords([st for st in stars if st.lightCurve])

            if c and not hasattr(c[0], "__iter__"):
                c = [[g] for g in c]

            if not coords:
                coords = c
            elif c and c[0]:
                if hasattr(c[0], "__iter__"):
                    coords = [list(a)+list(b) for a,b in zip(coords, c)]
                else:
                    coords = [[a] + [b] for a, b in zip(coords, c)]


        df_coords = pd.DataFrame(coords)

        df_coords.fillna(np.NaN)
        df_coords.dropna(inplace=True)

        space_coords = df_coords.values

        if not len(space_coords):
            return render(request, 'interface/error_page.html',
                          {
                              "error_m": "No space coordinates obtained from given stars. Check if input data files contain desired attribute."})

        axis = []
        for desc in ready_descriptors:
            if hasattr(desc.LABEL, "__iter__"):
                axis += desc.LABEL
            else:
                axis.append(desc.LABEL)

        all_axis = axis
        all_space_coords = [x.tolist() for x in space_coords.T]

        if deciders:

            act_decider.learn(space_coords)
            _probab_data = plotUnsupProbabSpace(
                space_coords, act_decider, "return", N=100)

            if _probab_data and len(_probab_data) == 4:
                xx, yy, Z, centroids = _probab_data
                probab_data = [xx.tolist(), yy.tolist(), Z.tolist()]

            elif _probab_data and len(_probab_data) == 5:
                xx, yy, Z, centroids, space_coords = _probab_data
                probab_data = [xx.tolist(), yy.tolist(), Z.tolist()]
                axis = ["Reduced dim 1", "Reduced dim 2"]

            elif _probab_data and len(_probab_data) == 3:
                xx, yy, centroids = _probab_data
                probab_data = [xx.tolist(), yy.tolist()]

            else:
                probab_data = []
                centroids = np.array([])
            centroids = list([c.tolist() for c in centroids.T])
            plot_title = act_decider.__class__.__name__
        else:
            probab_data = [[], [], []]
            centroids = [[], []]
            plot_title = "Space coordinates"

        coo_data = [x.tolist() for x in space_coords.T]

        return render(request, 'interface/unsupervised.html', {"page_title": PAGE_TITLE,
                                                               "page_info": PAGE_INFO2,
                                                               "point_labels": [],
                                                               "probab_data": probab_data,
                                                               "space_coords": all_space_coords,
                                                               "coo_data": coo_data,
                                                               "zeroes": [0 for _ in coo_data[0]],
                                                               "centroids": centroids,
                                                               "probab_plot_axis": axis,
                                                               "all_axis": all_axis,
                                                               "coo_plot_labels": st_info,
                                                               "probab_plot_title": plot_title,
                                                               "lcs": lcs,
                                                               "labels": [str(l) for l in labels]})

    else:
        descriptors = PackageReader().getClassesDict("descriptors")
        deciders = PackageReader().getClassesDict("unsup_deciders")
        descriptors_fields = getFields(descriptors)
        deciders_fields = getFields(deciders)

        desc_docs = deciders.copy()
        desc_docs.update(descriptors)
        click_obj_id = []
        popup_txt_id = []
        popup_cont = []
        for nam, val in descriptors_fields + deciders_fields:
            if val:
                click_obj_id.append(nam + "_head")
                popup_txt_id.append(nam + "_popup")

                doc_txt = desc_docs[nam].__doc__

                doc_txt = doc_txt.replace("    ", "&#09")
                doc_txt = doc_txt.replace("\n", "<br>")
                popup_cont.append(doc_txt)
        to_inter = zip(click_obj_id, popup_txt_id, popup_cont)

        return render(request, 'interface/unsupervised.html', {"page_title": PAGE_TITLE,
                                                               "page_info": PAGE_INFO1,
                                                               "descriptors": list(descriptors.keys()),
                                                               "deciders": list(deciders.keys()),
                                                               "descriptors_fields": descriptors_fields,
                                                               "deciders_fields": deciders_fields,
                                                               "to_inter": to_inter})
