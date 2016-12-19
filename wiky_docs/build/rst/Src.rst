
src package
***********


Subpackages
===========

* `src.bin package <Src.Bin>`_
  * `Submodules <Src.Bin#submodules>`_
  * `src.bin.build_data_structure module
    <Src.Bin#module-src.bin.build_data_structure>`_
  * `src.bin.filter_stars module
    <Src.Bin#src-bin-filter-stars-module>`_
  * `src.bin.make_filter module <Src.Bin#src-bin-make-filter-module>`_
  * `src.bin.plot_lcs module <Src.Bin#src-bin-plot-lcs-module>`_
  * `src.bin.prepare_query module
    <Src.Bin#module-src.bin.prepare_query>`_
  * `Module contents <Src.Bin#module-src.bin>`_
* `src.conf package <Src.Conf>`_
  * `Submodules <Src.Conf#submodules>`_
  * `src.conf.deciders_settings module
    <Src.Conf#module-src.conf.deciders_settings>`_
  * `src.conf.filter_loader module
    <Src.Conf#module-src.conf.filter_loader>`_
  * `src.conf.package_reader module
    <Src.Conf#module-src.conf.package_reader>`_
  * `src.conf.settings module <Src.Conf#module-src.conf.settings>`_
  * `Module contents <Src.Conf#module-src.conf>`_
* `src.db_tier package <Src.Db_Tier>`_
  * `Subpackages <Src.Db_Tier#subpackages>`_
    * `src.db_tier.connectors package <Src.Db_Tier.Connectors>`_
      * `Submodules <Src.Db_Tier.Connectors#submodules>`_
      * `src.db_tier.connectors.asas_archive module
        <Src.Db_Tier.Connectors#module-src.db_tier.connectors.asas_archive>`_
      * `src.db_tier.connectors.corot_archive module
        <Src.Db_Tier.Connectors#module-src.db_tier.connectors.corot_archive>`_
      * `src.db_tier.connectors.file_manager module
        <Src.Db_Tier.Connectors#module-src.db_tier.connectors.file_manager>`_
      * `src.db_tier.connectors.kepler_archive module
        <Src.Db_Tier.Connectors#module-src.db_tier.connectors.kepler_archive>`_
      * `src.db_tier.connectors.macho_client module
        <Src.Db_Tier.Connectors#module-src.db_tier.connectors.macho_client>`_
      * `src.db_tier.connectors.ogle_client module
        <Src.Db_Tier.Connectors#module-src.db_tier.connectors.ogle_client>`_
      * `Module contents
        <Src.Db_Tier.Connectors#module-src.db_tier.connectors>`_
  * `Submodules <Src.Db_Tier#submodules>`_
  * `src.db_tier.TAP_query module
    <Src.Db_Tier#module-src.db_tier.TAP_query>`_
  * `src.db_tier.base_query module
    <Src.Db_Tier#module-src.db_tier.base_query>`_
  * `src.db_tier.stars_provider module
    <Src.Db_Tier#src-db-tier-stars-provider-module>`_
  * `src.db_tier.vizier_tap_base module
    <Src.Db_Tier#module-src.db_tier.vizier_tap_base>`_
  * `Module contents <Src.Db_Tier#module-src.db_tier>`_
* `src.entities package <Src.Entities>`_
  * `Submodules <Src.Entities#submodules>`_
  * `src.entities.exceptions module
    <Src.Entities#module-src.entities.exceptions>`_
  * `src.entities.light_curve module
    <Src.Entities#module-src.entities.light_curve>`_
  * `src.entities.star module
    <Src.Entities#module-src.entities.star>`_
  * `Module contents <Src.Entities#module-src.entities>`_
* `src.stars_processing package <Src.Stars_Processing>`_
  * `Subpackages <Src.Stars_Processing#subpackages>`_
    * `src.stars_processing.deciders package
      <Src.Stars_Processing.Deciders>`_
      * `Submodules <Src.Stars_Processing.Deciders#submodules>`_
      * `src.stars_processing.deciders.base_decider module
        <Src.Stars_Processing.Deciders#module-src.stars_processing.deciders.base_decider>`_
      * `src.stars_processing.deciders.distance_desider module
        <Src.Stars_Processing.Deciders#module-src.stars_processing.deciders.distance_desider>`_
      * `src.stars_processing.deciders.neuron_decider module
        <Src.Stars_Processing.Deciders#module-src.stars_processing.deciders.neuron_decider>`_
      * `src.stars_processing.deciders.supervised_deciders module
        <Src.Stars_Processing.Deciders#module-src.stars_processing.deciders.supervised_deciders>`_
      * `Module contents
        <Src.Stars_Processing.Deciders#module-src.stars_processing.deciders>`_
    * `src.stars_processing.filters_impl package
      <Src.Stars_Processing.Filters_Impl>`_
      * `Submodules <Src.Stars_Processing.Filters_Impl#submodules>`_
      * `src.stars_processing.filters_impl.abbe_value module
        <Src.Stars_Processing.Filters_Impl#module-src.stars_processing.filters_impl.abbe_value>`_
      * `src.stars_processing.filters_impl.color_index module
        <Src.Stars_Processing.Filters_Impl#module-src.stars_processing.filters_impl.color_index>`_
      * `src.stars_processing.filters_impl.compare module
        <Src.Stars_Processing.Filters_Impl#module-src.stars_processing.filters_impl.compare>`_
      * `src.stars_processing.filters_impl.curve_density module
        <Src.Stars_Processing.Filters_Impl#module-src.stars_processing.filters_impl.curve_density>`_
      * `src.stars_processing.filters_impl.variogram_slope module
        <Src.Stars_Processing.Filters_Impl#module-src.stars_processing.filters_impl.variogram_slope>`_
      * `src.stars_processing.filters_impl.word_filters module
        <Src.Stars_Processing.Filters_Impl#module-src.stars_processing.filters_impl.word_filters>`_
      * `Module contents
        <Src.Stars_Processing.Filters_Impl#module-src.stars_processing.filters_impl>`_
    * `src.stars_processing.filters_tools package
      <Src.Stars_Processing.Filters_Tools>`_
      * `Submodules <Src.Stars_Processing.Filters_Tools#submodules>`_
      * `src.stars_processing.filters_tools.base_filter module
        <Src.Stars_Processing.Filters_Tools#module-src.stars_processing.filters_tools.base_filter>`_
      * `src.stars_processing.filters_tools.params_estim module
        <Src.Stars_Processing.Filters_Tools#module-src.stars_processing.filters_tools.params_estim>`_
      * `src.stars_processing.filters_tools.sax module
        <Src.Stars_Processing.Filters_Tools#module-src.stars_processing.filters_tools.sax>`_
      * `src.stars_processing.filters_tools.symbolic_representation
        module
        <Src.Stars_Processing.Filters_Tools#module-src.stars_processing.filters_tools.symbolic_representation>`_
      * `Module contents
        <Src.Stars_Processing.Filters_Tools#module-src.stars_processing.filters_tools>`_
    * `src.stars_processing.systematic_search package
      <Src.Stars_Processing.Systematic_Search>`_
      * `Submodules
        <Src.Stars_Processing.Systematic_Search#submodules>`_
      * `src.stars_processing.systematic_search.stars_searcher module
        <Src.Stars_Processing.Systematic_Search#src-stars-processing-systematic-search-stars-searcher-module>`_
      * `src.stars_processing.systematic_search.status_resolver module
        <Src.Stars_Processing.Systematic_Search#module-src.stars_processing.systematic_search.status_resolver>`_
      * `Module contents
        <Src.Stars_Processing.Systematic_Search#module-src.stars_processing.systematic_search>`_
  * `Submodules <Src.Stars_Processing#submodules>`_
  * `src.stars_processing.filtering_manager module
    <Src.Stars_Processing#module-src.stars_processing.filtering_manager>`_
  * `Module contents
    <Src.Stars_Processing#module-src.stars_processing>`_
* `src.tests package <Src.Tests>`_
  * `Submodules <Src.Tests#submodules>`_
  * `src.tests.test_connectors module
    <Src.Tests#src-tests-test-connectors-module>`_
  * `Module contents <Src.Tests#module-src.tests>`_
* `src.tools package <Src.Tools>`_
  * `Submodules <Src.Tools#submodules>`_
  * `src.tools.prepare_package module
    <Src.Tools#module-src.tools.prepare_package>`_
  * `Module contents <Src.Tools#module-src.tools>`_
* `src.utils package <Src.Utils>`_
  * `Submodules <Src.Utils#submodules>`_
  * `src.utils.commons module <Src.Utils#module-src.utils.commons>`_
  * `src.utils.data_analysis module
    <Src.Utils#module-src.utils.data_analysis>`_
  * `src.utils.helpers module <Src.Utils#module-src.utils.helpers>`_
  * `src.utils.output_process_modules module
    <Src.Utils#module-src.utils.output_process_modules>`_
  * `src.utils.stars module <Src.Utils#module-src.utils.stars>`_
  * `Module contents <Src.Utils#module-src.utils>`_

Submodules
==========


src.star module
===============


Module contents
===============
