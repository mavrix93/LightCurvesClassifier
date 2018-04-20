import os
import shutil
import sys

from unittest import mock

from lcc.bin.create_project import main as create_project
from lcc.bin.prepare_query import main as prepare_query
from lcc.bin.make_filter import main as make_filter
from lcc.bin.filter_stars import main as filter_stars
from lcc.cli.lcc import main as lcc_entry


def test_create_project_lcc():
    sys.argv = ["lcc", "create_project", "test_project_lcc2", "/tmp"]

    if os.path.exists("/tmp/test_project_lcc2"):
        shutil.rmtree("/tmp/test_project_lcc2")

    lcc_entry()

    assert os.path.exists("/tmp/test_project_lcc2/project_settings.py")


def test_create_project():
    sys.argv = ["lcc", "test_project_lcc", "/tmp"]

    if os.path.exists("/tmp/test_project_lcc"):
        shutil.rmtree("/tmp/test_project_lcc")

    create_project()

    assert os.path.exists("/tmp/test_project_lcc/project_settings.py")


def test_prepare_tuning():
    if os.path.exists("/tmp/tune_lc_shape.txt"):
        os.remove("/tmp/tune_lc_shape.txt")

    sys.argv = ["lcc",
                "prepare_query",
                "-o",
                "tune_lc_shape.txt",
                "-p",
                "CurvesShapeDescr:alphabet_size",
                "-r",
                "5:19:3",
                "-p" 
                "CurvesShapeDescr:days_per_bin",
                "-r",
                "30:120:40",
                "-p",
                "QDADec:threshold",
                "-r",
                "0.1:0.99:0.08",
                "-f",
                "/tmp"]

    config = mock.Mock()

    config.TUN_PARAMS = "/tmp"
    config.QUERIES = "/tmp"

    prepare_query(config)

    assert os.path.exists("/tmp/tune_lc_shape.txt")


def test_prepare_query_lcc():
    if os.path.exists("/tmp/query_ogle2.txt"):
        os.remove("/tmp/query_ogle2.txt")

    cmd = "lcc prepare_query -o query_ogle2.txt  -p starid -r 1:100 -p field_num -r 1:10 -p target -r lmc -f q"
    sys.argv = cmd.split()

    lcc_entry(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "resources"))

    assert os.path.exists("/tmp/query_ogle2.txt")


def test_prepare_query():
    if os.path.exists("/tmp/query_ogle.txt"):
        os.remove("/tmp/query_ogle.txt")

    cmd = "lcc prepare_query -o query_ogle.txt  -p starid -r 1:100 -p field_num -r 1:10 -p target -r lmc -f q"
    sys.argv = cmd.split()

    config = mock.Mock()

    config.TUN_PARAMS = "/tmp"
    config.QUERIES = "/tmp"

    prepare_query(config)

    assert os.path.exists("/tmp/query_ogle.txt")


def test_make_filter():
    if os.path.exists("/tmp/lcc_test/filters"):
        shutil.rmtree("/tmp/lcc_test/filters")

    cmd = """lcc make_filter -i tune_lc_shape.txt -f CurvesShapeDescr -s qso:50 -c be_stars:50 -t qso:1 -d QDADec -n CurveShapeFilter"""
    sys.argv = cmd.split()

    config = mock.Mock()
    config.TUN_PARAMS = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "resources")
    config.INP_LCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "sample")
    config.FILTERS = "/tmp/lcc_test/filters"

    make_filter(config)

    assert os.path.exists("/tmp/lcc_test/filters/CurveShapeFilter/CurveShapeFilter.filter")


def test_filter_stars():

    if os.path.exists("/tmp/lcc_test/results/TestRun/lcs"):
        shutil.rmtree("/tmp/lcc_test/results/TestRun/lcs")

    cmd = "lcc filter_stars.py -d OgleII -q query_ogle.txt -f CurveShapeFilter.filter -r TestRun"

    sys.argv = cmd.split()

    config = mock.Mock()
    config.QUERIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "resources")
    config.FILTERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "resources")
    config.RESULTS = "/tmp/lcc_test/results"

    filter_stars(config)

    assert os.path.exists("/tmp/lcc_test/results/TestRun/lcs")
    assert os.path.exists("/tmp/lcc_test/results/TestRun/lcs/LMC_SC1_1.fits")
    assert os.path.exists("/tmp/lcc_test/results/TestRun/lcs/LMC_SC5_1.fits")