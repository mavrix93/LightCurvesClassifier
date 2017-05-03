<!-- a resource descriptor containing services "running" external applets
or otherwise mainly spitting out templates with little manipulation.
-->

<resource resdir="__tests" schema="dc">
	<service id="specview" allowed="fixed">
		<meta name="title">Specview Applet Runner</meta>
		<nullCore/>
		<template key="fixed">//specview.html</template>
	</service>

	<service id="voplot" allowed="fixed">
		<meta name="title">VOPlot Applet Runner</meta>
		<nullCore/>
		<template key="fixed">//voplot.html</template>
	</service>
</resource>
