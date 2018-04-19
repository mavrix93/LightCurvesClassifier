from io import StringIO
import logging
import os
import time
import threading

import pandas as pd
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.shortcuts import render
from lcc.data_manager.package_reader import PackageReader
from lcc.stars_processing.systematic_search.stars_searcher import StarsSearcherRedis
from lcc.utils.output_process_modules import loadFromFile

from interface.helpers import parse_conn_combs, get_queries_from_df
from interface.helpers import query_dbs
from interface.models import DbQuery


MAX_RESULTS = 50

@login_required(login_url='login/')
def upload_form(request):
    PAGE_TITLE = "Querying and filtering of stars in databases"
    PAGE_INFO = '''For each connector you can use query text box. By default available keys
     are prefilled. You can query multiple connectors at once. <br><br>
    For more info about particular connectors you can click on the name of the selected connector
    on the right.
     <br><br>
    Parameters of queries are separated by new line (one parameter per line).
    Format: "parameter:from:to:step" or "parameter:from:to" or "parameter:value".<br>
    Example for OgleII:<br><br>
    starid:50:100<br>
    field_num:3:4<br>
    target:lmc<br><br>
    
    Common query for all databases:<br><br>
    
    ra:`5.549147 * 15`<br>
    dec:-70.55792<br>
    delta:5<br>
    nearest:`True`
    
    <br><br>
    Second option is use Python expresions. Lists and dictionaries are supported, just cover the query by "`".
    For example:<br>
    
    `[{"field":"LMC_SC1","starid":"152248","target":"lmc"}, {"field":"LMC_SC1","starid":"152","target":"lmc"}]`
    
    <br>
    is correct input. <br><br>
     
    The last option is to load query file. Which is csv file of queries. Columns represent database
    keys. Values should be comma separated. For example: <br>
    
    field,db,target,starid
    LMC_SC1,bvi,lmc,1
    LMC_SC5,bvi,lmc,1
    LMC_SC51,bvi,lmc,3

    '''

    if not request.POST.get("connectors_l"):
        try:
            PackageReader.appendModules("connectors",
                                        os.path.join(settings.MEDIA_ROOT,
                                                     str(request.user.id),
                                                     "my_modules",
                                                     "connectors"))
        except:
            logging.warning("This user doesn't have own modules")

        connectors = PackageReader().getClassesDict("connectors")

        avail_fields = []
        for con in connectors.values():
            if hasattr(con, "QUERY_OPTIONS"):
                avail_fields.append(":\n".join(con.QUERY_OPTIONS))
            else:
                avail_fields.append("")

        for i in range(len(avail_fields)):
            if avail_fields[i]:
                avail_fields[i] += ":"

        click_obj_id = []
        popup_txt_id = []
        popup_cont = []
        for nam, val in connectors.items():
            if val:
                click_obj_id.append(nam + "_head")
                popup_txt_id.append(nam + "_popup")
                doc_txt = val.__doc__
                doc_txt = doc_txt.replace("\t", "&#09")
                doc_txt = doc_txt.replace("    ", "&#09")
                doc_txt = doc_txt.replace("\n", "<br>")
                popup_cont.append(doc_txt)
        to_inter = zip(click_obj_id, popup_txt_id, popup_cont)
        return render(request, 'interface/search.html', {"page_title": PAGE_TITLE,
                                                         "page_info": PAGE_INFO,
                                                         "connectors": list(connectors.keys()),
                                                         "avail_fields": zip(list(connectors.keys()), avail_fields),
                                                         "to_inter": to_inter})
    else:

        ROOT = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "query_results")

        connector_names = request.POST.get("connectors_l", "").split(";")[:-1]

        query_file_queries = {}
        for con_name in connector_names:
            query_file_queries[con_name] = []
            query_files = request.FILES.getlist(con_name+"_query_file")

            for query_file in query_files:
                query_buffer = StringIO(query_file.read())

                query_file_queries[con_name] += get_queries_from_df(pd.read_csv(query_buffer))

        all_queries = parse_conn_combs(connector_names, request.POST)

        for db_key, q in query_file_queries.items():
            if db_key in all_queries:
                all_queries[db_key] += query_file_queries[db_key]
            else:
                all_queries[db_key] = query_file_queries[db_key]

        star_filters = [loadFromFile(
            filt_file.file) for filt_file in request.FILES.getlist("filter_file")]
        star_filter_names = [str(filt)
                             for filt in request.FILES.getlist("filter_file")]

        counter = 0
        for que in all_queries.values():
            counter += len(que)

        us = User.objects.get(pk=request.user.id)
        job = DbQuery.objects.create(user=us,
                                     connectors=";".join(connector_names),
                                     status="Running",
                                     queries=counter,
                                     used_filters=";".join(star_filter_names))

        job.save()
        job_id = str(job.id)

        job_path = os.path.join(ROOT, job_id)

        threading.Thread(target=query_dbs, args=(all_queries, job_path, job, star_filters)).start()
        return redirect('result', job_id=job_id)


@login_required(login_url='login/')
def show(request, job_id):
    queries_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "query_results")
    searcher = StarsSearcherRedis(stars_filters=None, db_connector=None, job_name="job:{}".format(job_id))

    try:
        job = DbQuery.objects.get(pk=job_id)
    except:
        job = None

    if job:

        job_path = os.path.join(queries_path, job_id)

        _job_info = {}
        _job_info["Connectors"] = job.connectors
        _job_info["Queries"] = job.queries
        _job_info["Started"] = str(job.start_date)[:-4]
        _job_info["Finished"] = str(job.finish_date)[:-4]
        _job_info["Status"] = job.status
        _job_info["Used filters"] = job.used_filters

        if job.status == "Failed":
            try:
                with open(os.path.join(job_path, "error.txt")) as f:
                    _job_info["Error message"] = f.read().replace("\n", " ")
            except:
                _job_info["Error message"] = "Unknown error occurred"

        job_info_df = pd.DataFrame([_job_info])
        job_info_df.index = ["info"]
        job_info_html = job_info_df.transpose().to_html()

        zip_url = ""
        status_table = ""
        if os.path.isfile(os.path.join(queries_path, job_id + ".zip")):
            df = searcher.getStatus()
            zip_url = "download/%s.zip" % job_id

            status_table = "<h1>Query status</h1>"
            for db_name in job.connectors.split(";"):
                status_table += "<h2>%s</h2>" % db_name

                if len(df.columns) and df.columns[0].startswith("#"):
                    df.rename(
                        columns={df.columns[0]: df.columns[0][1:]}, inplace=True)

                try:
                    passed_n = df['passed'].value_counts().get(True, 0), df['passed'].value_counts().get(False, 0)
                except KeyError:
                    passed_n = ("N/A", "N/A")

                if len(df) > MAX_RESULTS:
                    df = df[:MAX_RESULTS]

                df_table = df.to_html()
                status_table += df_table

        else:
            passed_n = ""

        df = searcher.getStatus(wait=False)
        num_queries = searcher._remaining_jobs() + len(df)
        return render(request, 'interface/results.html', {"connectors": job.connectors.split(";"),
                                                          "job_id": job_id,
                                                          "num_queries": job.queries,
                                                          "zip_url": zip_url,
                                                          "status_table": status_table,
                                                          "job_info_html": job_info_html,
                                                          "act_num_queries": num_queries,
                                                          "passed_n": passed_n})
    else:
        em = "Job %s doesn't exist" % job_id
        return render(request, 'interface/error_page.html', {"error_m": em})
