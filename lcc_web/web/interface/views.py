import glob
import os
import shutil

import pandas as pd
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import render_to_response
from django.template import RequestContext


from interface.forms import LoginForm
from interface.models import DbQuery
from interface.models import StarsFilter

pd.set_option('display.max_colwidth', -1)


# TODO
def handler404(request):
    response = render_to_response('interface/404.html', {},
                                  context_instance=RequestContext(request))
    response.status_code = 404
    return response


def handler500(request):
    response = render_to_response('interface/500.html', {},
                                  context_instance=RequestContext(request))
    response.status_code = 500
    return response


@login_required(login_url='login/')
def manage_modules(request):
    PAGE_INFO = ""

    if request.method != 'POST':
        descr_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "my_modules", "descriptors")
        con_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "my_modules", "connectors")
        deci_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), "my_modules", "deciders")

        descriptors = glob.glob(descr_path+"/*py")
        connectors = glob.glob(con_path + "/*py")
        deciders = glob.glob(deci_path + "/*py")

        descriptors = [d.split("/")[-1] for d in descriptors if not d.endswith("__init__.py")]
        deciders = [d.split("/")[-1] for d in deciders if not d.endswith("__init__.py")]
        connectors = [d.split("/")[-1] for d in connectors if not d.endswith("__init__.py")]

        descriptors_cont = []
        for des in descriptors:
            with open(os.path.join(descr_path, des)) as fi:
                descriptors_cont.append(fi.read())

        cone_cont = []
        for des in connectors:
            with open(os.path.join(con_path, des)) as fi:
                cone_cont.append(fi.read())

        deci_cont = []
        for des in deciders:
            with open(os.path.join(deci_path, des)) as fi:
                deci_cont.append(fi.read())

        return render(request, 'interface/manage_modules.html', {"page_title": "Manage modules",
                                                                 "page_info": PAGE_INFO,
                                                                 "deciders" : deciders,
                                                                 "descriptors" : descriptors,
                                                                 "connectors" : connectors,
                                                                 "descr_path" : descr_path,
                                                                 "con_path" :con_path,
                                                                 "deci_path" : deci_path,
                                                                 "descriptors_cont" : descriptors_cont,
                                                                 "cone_cont" : cone_cont,
                                                                 "dec_cont" : deci_cont})
    elif "delete_but" in request.POST.keys():
        os.remove(request.POST.get("mod_path"))
        return redirect(manage_modules)

    else:
        path = request.POST.get("mod_path")
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        with open(path, "w") as fi:
            fi.write(request.POST.get("module_cont"))
        return redirect(manage_modules)


def create_user(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user_folder = os.path.join(settings.MEDIA_ROOT, str(request.user.id))
            if not os.path.exists(user_folder):
                os.makedirs(user_folder)
            form.save()
            return redirect("home")
        return render(request, 'interface/error_page.html', {"error_m": form.errors})

    else:
        form = UserCreationForm()
        return render(request, 'interface/create_user.html', {'form': form})


def contact(request):
    return render(request, "interface/contact.html", {})


def guide(request):
    info = ""
    return render(request, "interface/guide_page.html", {"info": info})


def show_logs(request):
    if request.user.is_authenticated():
        groups = [g.name for g in request.user.groups.all()]
        if "admin_gr" in groups:
            log_file = request.GET.get('name')
            if log_file:
                with open(os.path.join(os.environ.get("DOCKYARD_SRVLOGS"), log_file+".log")) as fi:
                    log_cont = fi.readlines()
                return HttpResponse(log_cont, content_type='text/plain')
                
            else:
                return render(request, 'interface/error_page.html', {"error_m": "Queried log file doesn't exists"})
                
        else:
            return render(request, 'interface/error_page.html', {"error_m": "You have no permission to see logs"})
    else:
        return render(request, 'interface/error_page.html', {"error_m": "You are not logged"})


def logout_view(request):
    logout(request)
    return redirect("home")


def login_view(request):
    if request.method == 'GET':
        goto = request.GET.get("next", "home")
    else:
        goto = "home"

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = LoginForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            username = request.POST['user_name']
            password = request.POST['password']
            goto = request.POST['goto_f']
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
            else:
                return render(request, 'interface/error_page.html', {"error_m": "Invalid user name or/and password"})

            user_folder = os.path.join(settings.MEDIA_ROOT, str(request.user.id))
            if not os.path.exists(user_folder):
                os.makedirs(user_folder)

            return redirect(goto)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = LoginForm()
    return render(request, 'interface/login.html', {'form': form, "goto": goto})


def delete_job(request, job_type, job_id):
    if job_type == "stars_filter":
        try:
            red_to = "all_filters"
            fold = "stars_filters"
            StarsFilter.objects.get(pk=job_id).delete()

        except:
            pass
    elif job_type == "result":
        try:
            red_to = "all_results"
            fold = "query_results"
            DbQuery.objects.get(pk=job_id).delete()

        except:
            pass
    else:
        return render(request, 'interface/error_page.html', {"error_m": "Unresolved job type. You can delete stars filter or query result"})

    try:
        shutil.rmtree(os.path.join(settings.MEDIA_ROOT, fold, job_id))
    except OSError:
        pass

    return redirect(red_to)


def home(request):
    user_name = request.user.username
    if not user_name:
        info = "You are not logged"
    else:
        info = "You are logged as %s" % user_name
    return render(request, "interface/index.html", {"info": info})
