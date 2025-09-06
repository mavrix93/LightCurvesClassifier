import importlib
import interface.views as views
try:
    from django.conf.urls import url  # Django 1.x compatibility
except ImportError:
    from django.urls import re_path as url

def _lazy(module_name, attr):
    def _wrapped(*args, **kwargs):
        module = importlib.import_module(module_name)
        return getattr(module, attr)(*args, **kwargs)
    return _wrapped

urlpatterns = [
    url(r'^$', views.home, name='home'),
    url(r'^manage_modules', views.manage_modules, name='manage_modules'),
    url(r'^new_user', views.create_user, name='create_user'),
    url(r'^contact', views.contact, name='contact'),
    url(r'^guide', views.guide, name='guide'),
    url(r'^logs', views.show_logs, name='show_logs'),
    url(r'^login', views.login_view, name='login_view'),
    url(r'^logout', views.logout_view, name='logout_view'),
    url(r'^show', _lazy('interface.lcc_views.visualization', 'stars'), name='show'),
    url(r'^unsup', _lazy('interface.lcc_views.visualization', 'unsup_clust'), name='unsup'),
    url(r'^make_filter$', _lazy('interface.lcc_views.filtering', 'upload_form'), name='make_filter'),
    url(r'^delete/(?P<job_type>\D+)/(?P<job_id>\d+)',
        views.delete_job, name='delete_job'),
    url(r'^stars_filter/(?P<job_id>[a-zA-Z0-9]*)',
        _lazy('interface.lcc_views.filtering', 'show'), name='stars_filter'),
    url(r'^search', _lazy('interface.lcc_views.searching', 'upload_form'), name='search'),
    url(r'^result/(?P<job_id>[a-zA-Z0-9]*)', _lazy('interface.lcc_views.searching', 'show'), name='result'),
    url(r'^stars_filters', _lazy('interface.lcc_views.jobs', 'all_filters'), name='all_filters'),
    url(r'^results*', _lazy('interface.lcc_views.jobs', 'all_results'), name='all_results'),
    url(r'^download/(?P<file_name>[a-zA-Z0-9]*)', _lazy('interface.lcc_views.jobs', 'download_file'), name='download')]


# run_workers(n_workers=int(os.environ.get("LCC_RQ_WORKERS", 1)))
