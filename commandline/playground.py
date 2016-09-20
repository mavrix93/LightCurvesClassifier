from conf.package_reader import PackageReader

a =  PackageReader().getClasses("connectors")

for cl in a:
    print cl.__name__