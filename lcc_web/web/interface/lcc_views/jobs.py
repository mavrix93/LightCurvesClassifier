import glob
import json
import os
from wsgiref.util import FileWrapper
import shutil

import pandas as pd
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse
from django.shortcuts import render

from interface.models import DbQuery
from interface.models import StarsFilter


@login_required(login_url='login/')
def all_filters(request):
    stars_filters_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "stars_filters")

    header = ["Job id", "Status", "Start date",
              "Finish date", "Descriptors", "Deciders", "Link"]
    dat = []
    for star_filt in StarsFilter.objects.filter(user=request.user):
        row = [star_filt.id,
               star_filt.status,
               str(star_filt.start_date),
               str(star_filt.finish_date),
               star_filt.descriptors.replace(";", "<br>"),
               star_filt.deciders,
               str(star_filt.id)]
        dat.append(row)

    table = pd.DataFrame(
        dat, columns=["fold_name", "status", "start", "stop", "descr", "decid", "job_id"])
    table["start"] = pd.to_datetime(table["start"])
    table.sort_values(by="start", ascending=False, inplace=True)

    job_ids = table["job_id"].values.tolist()
    table = table.drop('job_id', 1)
    return render(request, 'interface/jobs.html', {"page_title": "Star filter jobs",
                                                   "header": header,
                                                   "stars_filter": True,
                                                   "delete_prefix" : '"../{}/delete/"'.format(os.environ.get(
                                                       "DOCKYARD_APP_CONTEXT"), ""),
                                                   "table": zip(table.values.tolist(), job_ids)})


@login_required(login_url='login/')
def _all_filters(request):
    stars_filters_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "stars_filters")

    header = ["Job id", "Status", "Date", "Descriptors", "Deciders", "Link"]
    dat = []
    for folder_name in os.listdir(stars_filters_path):
        try:
            with open(os.path.join(stars_filters_path, folder_name, "status.json"), 'r') as status_file:
                status = json.load(status_file)
            row = [folder_name,
                   status.get("status", ""),
                   status.get("start", ""),
                   status.get("descriptors", ""),
                   status.get("deciders", ""),
                   str(folder_name)]

            dat.append(row)
        except:
            pass
    table = pd.DataFrame(
        dat, columns=["fold_name", "status", "start", "descr", "decid", "job_id"])
    table["start"] = pd.to_datetime(table["start"])
    table.sort_values(by="start", ascending=False, inplace=True)

    job_ids = table["job_id"].values.tolist()
    table = table.drop('job_id', 1)
    return render(request, 'interface/jobs.html', {"page_title": "Star filter jobs",
                                                   "header": header,
                                                   "stars_filter": True,
                                                   "table": zip(table.values.tolist(), job_ids)})


@login_required(login_url='login/')
def all_results(request):
    queries_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "query_results")
    header = ["Job id", "Status", "Started",
              "Finished", "Queries", "Connectors", "Link"]

    dat = []
    for query in DbQuery.objects.filter(user=request.user):
        row = [query.id,
               query.status,
               str(query.start_date),
               str(query.finish_date),
               str(query.queries),
               query.connectors,
               str(query.id)]
        dat.append(row)

    table = pd.DataFrame(
        dat, columns=["fold_name", "status", "started", "finished", "queries", "conn", "job_id"])
    table["started"] = pd.to_datetime(table["started"])
    table.sort_values(by="started", ascending=False, inplace=True)

    job_ids = table["job_id"].values.tolist()
    table = table.drop('job_id', 1)

    return render(request, 'interface/jobs.html', {"page_title": "Queries jobs",
                                                   "stars_filter": False,
                                                   "header": header,
                                                   "delete_prefix": '"../{}/delete/"'.format(os.environ.get(
                                                       "DOCKYARD_APP_CONTEXT")),
                                                   "table": zip(table.values.tolist(), job_ids)})


def download_file(request, file_name):
    """
    Send a file through Django without loading the whole file into
    memory at once. The FileWrapper will turn the file object into an
    iterator for chunks of 8KB.
    """
    if file_name.startswith("estim"):
        file_type = "estim"
        file_name = file_name[9:]
        filename = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "stars_filters", file_name, "estimator")

    elif not file_name.startswith("filt"):
        file_type = "query"
        filename = os.path.join(
            settings.MEDIA_ROOT, str(request.user.id), "query_results", file_name + ".zip")

    else:
        file_type = "filter"
        file_name = file_name[4:]
        
        pa = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "stars_filters", file_name)
        
        filter_names = glob.glob(pa + "/*.filter")

        if filter_names:
            filter_name = os.path.basename(filter_names[0])
            filename = os.path.join(
                settings.MEDIA_ROOT, str(request.user.id), "stars_filters", file_name, filter_name)
        else:
            return render(request, 'interface/error_page.html', {"error_m": "There is no filter in %s" % file_name})

    wrapper = FileWrapper(open(filename, 'rb'))
    response = HttpResponse(wrapper, content_type='text/plain')
    response['Content-Length'] = os.path.getsize(filename)
    if file_type == "filter":
        response[
            'Content-Disposition'] = 'attachment; filename="%s.filter"' % filter_name

    elif file_type == "estim":
        response[
            'Content-Disposition'] = 'attachment; filename="estimator"'

    else:
        response[
            'Content-Disposition'] = 'attachment; filename="results_%s.zip"' % file_name
    return response
