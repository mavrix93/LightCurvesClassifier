<resource schema="__system">
	<meta name="description">Various RD elements for publication and
	manipulation of Echelle spectra.

	Very briefly, Echelle spectra come in single-order varieties or joined.
	The joined spectra can be dealt with using just whats in //ssap.  It's
	the split-order varieties we're talking about here.

	The recommended way to deal with them is to pull all measurements into
	database tables and generate VOTables containing the requested orders
	on the fly.  You'll still need SSA-like tables for them, but with
	some additional columns.
	</meta>

	<STREAM id="ssacols">
		<doc>
			Additional columns for SSA metadata tables describing Echelle
			spectra.
		</doc>
		<column name="n_orders" type="integer"
				ucd="meta.number"
				tablehead="#Orders"
				description="Number of orders in the spectrum."
				verbLevel="15">
			<values nullLiteral="-1"/>
		</column>
		<column name="order_min" type="integer"
				ucd="meta.min;meta.number"
				tablehead="Min. Order"
				description="Minimal Echelle order in the spectrum."
				verbLevel="15">
			<values nullLiteral="-1"/>
		</column>
		<column name="order_max" type="integer"
			ucd="meta.max;meta.number"
			tablehead="Max. Order"
			description="Maximal Echelle order in the spectrum."
			verbLevel="15">
			<values nullLiteral="-1"/>
		</column>
	</STREAM>

	<procDef id="setSSAMeta" type="apply">
		<doc>
			A rowmaker apply to fill the columns inserted with //echelle#ssacols.
		</doc>
		<setup>
			<par name="n_orders" description="Number of orders in the spectrum"
				late="True"/>
			<par name="order_min" late="True"
				description="First Echelle order in the spectrum"/>
			<par name="order_max" late="True"
				description="Last Echelle order in the spectrum"/>
		</setup>
		<code>
			result["n_orders"] = n_orders
			result["order_min"] = order_min
			result["order_max"] = order_max
		</code>
	</procDef>
</resource>
