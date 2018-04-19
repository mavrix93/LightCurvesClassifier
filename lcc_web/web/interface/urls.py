import interface.views as views
from django.conf.urls import url
from interface.lcc_views import jobs, searching, filtering, visualization

urlpatterns = [
    url(r'^$', views.home, name='home'),
    url(r'^manage_modules', views.manage_modules, name='manage_modules'),
    url(r'^new_user', views.create_user, name='create_user'),
    url(r'^contact', views.contact, name='contact'),
    url(r'^guide', views.guide, name='guide'),
    url(r'^logs', views.show_logs, name='show_logs'),
    url(r'^login', views.login_view, name='login_view'),
    url(r'^logout', views.logout_view, name='logout_view'),
    url(r'^show', visualization.stars, name='show'),
    url(r'^unsup', visualization.unsup_clust, name='unsup'),
    url(r'^make_filter$', filtering.upload_form, name='make_filter'),
    url(r'^delete/(?P<job_type>\D+)/(?P<job_id>\d+)',
        views.delete_job, name='delete_job'),
    url(r'^stars_filter/(?P<job_id>[a-zA-Z0-9]*)',
        filtering.show, name='stars_filter'),
    url(r'^search', searching.upload_form, name='search'),
    url(r'^result/(?P<job_id>[a-zA-Z0-9]*)', searching.show, name='result'),
    url(r'^stars_filters', jobs.all_filters, name='all_filters'),
    url(r'^results*', jobs.all_results, name='all_results'),
    url(r'^download/(?P<file_name>[a-zA-Z0-9]*)', jobs.download_file, name='download')]


# run_workers(n_workers=int(os.environ.get("LCC_RQ_WORKERS", 1)))
