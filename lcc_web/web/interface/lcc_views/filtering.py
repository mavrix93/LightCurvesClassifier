import json
import logging
import os
import threading
from copy import deepcopy

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.shortcuts import render
from lcc.data_manager.package_reader import PackageReader
from lcc.utils.output_process_modules import loadFromFile

from interface.helpers import create_filter, load_test_stars
from interface.helpers import getFields
from interface.helpers import make_data_file
from interface.helpers import parse_combinations
from interface.helpers import parse_comp_stars
from interface.helpers import parse_stars
from interface.models import StarsFilter


@login_required(login_url='login/')
def upload_form(request, warning=""):
    PAGE_TITLE = "Make filter"
    PAGE_INFO = """There are text input per every parameter of descriptors and deciders. You can specify
    one value or range of values in following format:<br>
    "from":"to":"step_num" or "from":"to" (in this case length of step is taken as one) or "value1";"value2";"value3";...etc<br><br>
    
    For evaluating content as python code wrapp the code into "`". For example:<br><br>
    
    `True` - bool value (not string)<br>
    `7*6` - integer (42)<br>
    `[("b_mag","v_mag"),("r_mag","i_mag")]` - list of tuples of strings<br><br>
    
    It is possible to select multiple descriptors and deciders. <br>
    <br>
    NOTE that it raises error if loaded stars dont contain desired attribute (light curve, color index etc)"""

    if (request.POST.get("descriptors_l", "").split(";")[:-1]
            and request.POST.get("deciders_l", "").split(";")[:-1]):
        return post_form(request)

    try:
        PackageReader.appendModules("deciders",
                                    os.path.join(settings.MEDIA_ROOT,
                                                 str(request.user.id),
                                                 "my_modules",
                                                 "deciders"))
    except:
        logging.warn("This user doesn't have own modules")


    try:
        PackageReader.appendModules("descriptors",
                                    os.path.join(settings.MEDIA_ROOT,
                                                 str(request.user.id),
                                                 "my_modules",
                                                 "descriptors"))
    except:
        logging.warning("This user doesn't have own modules")

    descriptors = PackageReader().getClassesDict("descriptors")
    deciders = PackageReader().getClassesDict("deciders")
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
            doc_txt = doc_txt.replace("\t", "&#09")
            doc_txt = doc_txt.replace("    ", "&#09")
            doc_txt = doc_txt.replace("\n", "<br>")
            popup_cont.append(doc_txt)
    to_inter = zip(click_obj_id, popup_txt_id, popup_cont)

    return render(request, 'interface/make_filter.html', {"page_title": PAGE_TITLE,
                                                          "page_info": PAGE_INFO,
                                                          "descriptors": list(descriptors.keys()),
                                                          "deciders": list(deciders.keys()),
                                                          "descriptors_fields": descriptors_fields,
                                                          "deciders_fields": deciders_fields,
                                                          "warning": warning,
                                                          "to_inter": to_inter})


@login_required(login_url='login/')
def post_form(request):
    search_fi = request.FILES.getlist("search_file")
    cont_fi = request.FILES.getlist("cont_file")

    descriptor_names = request.POST.get("descriptors_l", "").split(";")[:-1]
    deciders_names = request.POST.get("deciders_l", "").split(";")[:-1]

    tuned_params, _static_params = parse_combinations(
        descriptor_names + deciders_names, request.POST, split_by=":")
    static_params = parse_comp_stars(request.FILES)

    if descriptor_names and deciders_names:

        for key, value in _static_params.items():
            if key in static_params:
                static_params[key].update(value)
            else:
                static_params[key] = value

        try:
            if not search_fi or not cont_fi:
                searched_stars = load_test_stars(os.path.join(settings.TEST_SAMPLE, "sample1"))
                contamination_stars = load_test_stars(os.path.join(settings.TEST_SAMPLE, "sample2"))

            else:
                searched_stars = parse_stars(search_fi)
                contamination_stars = parse_stars(cont_fi)
        except:
            return render(request, 'interface/error_page.html', {"error_m": "Couldn't parse star files"})

        if not searched_stars or not contamination_stars:
            return render(request, 'interface/error_page.html',
                          {"error_m": "Missing stars. You have to load both searched sample and contamination sample."})

        split_ratio_err = False
        split_ratio = float(request.POST.get("split_ratio", "0.8"))
        try:
            if split_ratio > 1 or split_ratio < 0:
                split_ratio_err = True
        except ValueError:
            split_ratio_err = True

        if split_ratio_err:
            return render(request, 'interface/error_page.html',
                          {"error_m": "Invalid split ratio. It has to be float number in range of 0 and 1"})

        deciders = [desc for desc in PackageReader().getClasses(
                    "deciders") if desc.__name__ in deciders_names]
        descriptors = [desc for desc in PackageReader().getClasses(
            "descriptors") if desc.__name__ in descriptor_names]

        us = User.objects.get(pk=request.user.id)
        job = StarsFilter.objects.create(user=us,
                                         deciders=";".join(
                                             [dec.__name__ for dec in deciders]),
                                         descriptors=";".join([dec.__name__ for dec in descriptors]))
        job.save()
        job_id = str(job.id)

        threading.Thread(target=create_filter, args=(searched_stars, contamination_stars, descriptors, deciders,
                                                     tuned_params, static_params, job, split_ratio,
                                                     str(request.user.id))).start()

        return redirect('stars_filter', job_id=job_id)

    return upload_form(request, warning="You have to select at least one descriptor and one decider")


@login_required(login_url='login/')
def show(request, job_id):
    PAGE_TITLE = "Result screen"
    PAGE_INFO = """You can aim cursor to a point in probability plot to see additional<br>
    information about the star. You can also click on it to see the light curve<br><br>
    Also you can modify the probability plot by GET request on this url. Supported key:
    <br>
    N - Resoulution of the graph <br>
    xmax, xmin, ymax, ymin - Borders of the graph <br>
    <br>
    Example for increasing resolution to 1000 x 1000 points: <br>
    https://vocloud-dev.asu.cas.cz/lcc/stars_filter/115?N=1000"""

    try:
        job = StarsFilter.objects.get(pk=job_id)
    except StarsFilter.DoesNotExist:
        msg = "Stars filter job with id %i doesn't exist" % job_id
        return render(request, 'interface/error_page.html', {"error_m": msg})

    if job.user.id != request.user.id:
        msg = "Permission denied: This job wasn't created by you!"
        return render(request, 'interface/error_page.html', {"error_m": msg})

    try:
        with open(os.path.join(settings.MEDIA_ROOT, str(request.user.id), "stars_filters", job_id, 'error.txt'), 'r') as err_file:
            err_msg = err_file.read()
    except:
        err_msg = "---"

    status_info = job.status
    try:
        with open(os.path.join(settings.MEDIA_ROOT, str(request.user.id), "stars_filters", job_id, 'info.json'), 'r') as info_file:
            info = json.load(info_file)
    except:
        info = {}

    status = dict()
    status["status"] = job.status
    status["descriptors"] = job.descriptors
    status["deciders"] = job.deciders
    status["start"] = str(job.start_date)[:-4]
    status["finish"] = str(job.finish_date)[:-4]

    if status_info == "Done":
        try:
            with open(os.path.join(settings.MEDIA_ROOT, str(request.user.id), "stars_filters", job_id, 'data.json')) as data_file:
                data = json.load(data_file)

            filt_id = int(request.GET.get('filtid', data.get("best_id", 0)))
            N = request.GET.get('N')
            xmax = request.GET.get('xmax')
            xmin = request.GET.get('xmin')
            ymax = request.GET.get('ymax')
            ymin = request.GET.get('ymin')
            again = request.GET.get('again')

            data_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "stars_filters", job_id, "data_%i.json" % filt_id)

            # if filt_id == data.get("best_id") and not os.path.exists(data_path):
            #    data_path = os.path.join(settings.MEDIA_ROOT, "stars_filters", job_id, "data.json")

            if not os.path.exists(data_path) or xmax or xmin or ymax or ymin or N or again:
                estim = loadFromFile(os.path.join(settings.MEDIA_ROOT, str(request.user.id), "stars_filters", job_id, 'estimator'))
                if filt_id >= len(estim.filters):
                    return  render(request, 'interface/error_page.html',
                                   {"error_m": "Given filter id is greater then number of filters"})

                make_data_file(estim, filt_id, data_path, N, xmax, xmin, ymax, ymin)

            with open(data_path) as data_file:
                data.update(json.load(data_file))

            data["filt_id"] = filt_id

        except Exception as e:
            raise

    if status_info == "Done":
        if "coo_plot_labels" in data:
            data["coo_plot_labels"] = [str(lab)
                                       for lab in data["coo_plot_labels"]]

        if "labels" in data:
            data["labels"] = [str(lab) for lab in data["labels"]]

        if "point_labels" in data:
            data["point_labels"] = [
                [str(x) for x in lab] for lab in data["point_labels"]]

        data.update(status)
        data.update(info)
        data["status_info"] = status_info

    else:
        data = status
        data.update(info)

    if "status_info" not in data:
        data["status_info"] = status_info

    if status_info == "Done":
        data["probab_plot_axis"] = [str(ax) for ax in data["probab_plot_axis"]]
        coo_data = data.get("coo_data")

    if data.get("coo_data") and len(data["probab_plot_axis"]) > len(data.get("coo_data")[0]):
        data["all_axis"] = deepcopy(data["probab_plot_axis"])
        data["probab_plot_axis"] = ["<br>".join(data["probab_plot_axis"])] + ["" for _ in range(len(coo_data[0]) - 1)]

    data["job_id"] = job_id
    data["err_msg"] = err_msg
    data["page_title"] = PAGE_TITLE
    data["page_info"] = PAGE_INFO

    data["colors"] = ["#105e06", "#13a300", "#f29109", "#f9ef25"]

    return render(request, "interface/show_stars_filter.html", data)
