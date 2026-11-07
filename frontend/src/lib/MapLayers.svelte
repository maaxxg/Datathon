<script>
	import { onMount } from "svelte";
	import { MAP_LEGEND, MAP_UNAVAILABLE } from "$lib/labels.js";

	let { map, requestedLayer = null } = $props();

	const HV_MIN_ZOOM = 12;
	const HV_MAX_ZOOM = 15;
	const API = "/api/map-data";
	// Bottom to top. Marker is a DOM element, always above.
	const ORDER = [
		"efas-layer",
		"hv-flood-layer",
		"geo-susc-fill",
		"geo-susc-line",
		"geo-unf-fill",
		"geo-unf-line",
		"geo-coverage-line",
	];

	let sources = $state({});
	let mapZoom = $state(12);

	let showHv = $state(false);
	let hvScenario = $state("srednja");
	let showGeo = $state(false);
	let geoLayer = $state("landslide");
	let showUnf = $state(false);
	let showEfas = $state(false);
	let efasRp = $state("100");
	let unavailable = $state({ geo: false, efas: false });

	let efasBounds = null;
	const geoCache = {};

	onMount(async () => {
		try {
			const res = await fetch("/api/sources");
			if (res.ok) sources = (await res.json()).layers || {};
		} catch {
			/* attribution falls back to empty; the legend still shows */
		}
	});

	$effect(() => {
		if (!map) return;
		const onZoom = () => (mapZoom = map.getZoom());
		map.on("zoom", onZoom);
		mapZoom = map.getZoom();
		return () => map.off("zoom", onZoom);
	});

	$effect(() => {
		if (!map || !requestedLayer || !requestedLayer.key) return;
		const key = requestedLayer.key;
		if (key === "flood_hv" || key === "flood") {
			showHv = true;
			updateHv();
		} else if (key === "flood_efas") {
			showEfas = true;
			updateEfas();
		} else if (
			key === "landslide" ||
			key === "liquefaction" ||
			key === "sinkhole"
		) {
			showGeo = true;
			geoLayer = key;
			updateGeo();
		} else if (key === "unfavourable") {
			showGeo = true;
			showUnf = true;
			updateGeo();
		}
	});

	function attr(key) {
		const s = sources[key];
		return s ? `${s.publisher} (${s.year})` : "";
	}

	function beforeIdFor(id) {
		for (const next of ORDER.slice(ORDER.indexOf(id) + 1))
			if (map.getLayer(next)) return next;
		return undefined;
	}

	function addLayer(spec) {
		map.addLayer(spec, beforeIdFor(spec.id));
	}

	function removeAll(layerIds, sourceIds) {
		for (const l of layerIds) if (map.getLayer(l)) map.removeLayer(l);
		for (const s of sourceIds) if (map.getSource(s)) map.removeSource(s);
	}

	async function getJson(name) {
		if (geoCache[name]) return geoCache[name];
		const res = await fetch(`${API}/${name}`);
		if (!res.ok) throw new Error("unavailable");
		return (geoCache[name] = await res.json());
	}

	// ---- HV flood WMS (EPSG:3857, 256 px)
	function updateHv() {
		if (!map) return;
		removeAll(["hv-flood-layer"], ["hv-flood-wms"]);
		if (!showHv) return;
		const wmsLayer = `poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-${hvScenario}-vjerojatnost_2019`;
		const tileUrl =
			`https://servisi.voda.hr/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap` +
			`&LAYERS=${wmsLayer}&STYLES=&CRS=EPSG:3857&BBOX={bbox-epsg-3857}` +
			`&WIDTH=256&HEIGHT=256&FORMAT=image/png&TRANSPARENT=true`;
		map.addSource("hv-flood-wms", {
			type: "raster",
			tiles: [tileUrl],
			tileSize: 256,
			attribution: attr("flood_hv")
				? `© ${attr("flood_hv")}`
				: "© Hrvatske vode",
		});
		addLayer({
			id: "hv-flood-layer",
			type: "raster",
			source: "hv-flood-wms",
			minzoom: HV_MIN_ZOOM,
			maxzoom: HV_MAX_ZOOM,
			paint: { "raster-opacity": 0.72 },
		});
	}

	// ---- MPGI geohazards (simplified GeoJSON served by our API, EPSG:4326 lon,lat)
	const GEO_LAYERS = [
		"geo-susc-fill",
		"geo-susc-line",
		"geo-unf-fill",
		"geo-unf-line",
		"geo-coverage-line",
	];
	const GEO_SOURCES = ["geo-susc", "geo-unf", "geo-coverage"];
	let geoToken = 0;
	let efasToken = 0;

	// Group failure: remove every layer/source and clear the legend so map and legend never disagree.
	function failGeo() {
		removeAll(GEO_LAYERS, GEO_SOURCES);
		showGeo = false;
		showUnf = false;
		unavailable.geo = true;
	}

	async function updateGeo() {
		if (!map) return;
		const token = ++geoToken;
		unavailable.geo = false;
		if (!showGeo) {
			removeAll(GEO_LAYERS, GEO_SOURCES);
			showUnf = false;
			return;
		}
		try {
			const [data, cov, unf] = await Promise.all([
				getJson(`geohazard_${geoLayer}.geojson`),
				getJson("banovina_coverage.geojson"),
				showUnf ? getJson("geohazard_unfavourable.geojson") : null,
			]);
			if (token !== geoToken) return; // stale response
			const attribution = attr(geoLayer)
				? `© ${attr(geoLayer)}`
				: "© MPGI";
			if (map.getSource("geo-susc")) {
				map.getSource("geo-susc").setData(data);
			} else {
				map.addSource("geo-susc", {
					type: "geojson",
					data,
					attribution,
				});
				const colour = [
					"match",
					["get", "podloznost"],
					"niska",
					"#facc15",
					"srednja",
					"#f97316",
					"visoka",
					"#b91c1c",
					"#6b7280",
				];
				addLayer({
					id: "geo-susc-fill",
					type: "fill",
					source: "geo-susc",
					paint: { "fill-color": colour, "fill-opacity": 0.45 },
				});
				addLayer({
					id: "geo-susc-line",
					type: "line",
					source: "geo-susc",
					paint: { "line-color": colour, "line-width": 1 },
				});
			}
			if (!map.getSource("geo-coverage")) {
				map.addSource("geo-coverage", { type: "geojson", data: cov });
				addLayer({
					id: "geo-coverage-line",
					type: "line",
					source: "geo-coverage",
					paint: {
						"line-color": "#0f766e",
						"line-width": 2,
						"line-dasharray": [3, 2],
					},
				});
			}
			removeAll(["geo-unf-fill", "geo-unf-line"], ["geo-unf"]);
			if (unf) {
				map.addSource("geo-unf", {
					type: "geojson",
					data: unf,
					attribution: attr("unfavourable")
						? `© ${attr("unfavourable")}`
						: "© MPGI",
				});
				addLayer({
					id: "geo-unf-fill",
					type: "fill",
					source: "geo-unf",
					paint: { "fill-color": "#4c1d95", "fill-opacity": 0.35 },
				});
				addLayer({
					id: "geo-unf-line",
					type: "line",
					source: "geo-unf",
					paint: { "line-color": "#4c1d95", "line-width": 2 },
				});
			}
		} catch {
			if (token === geoToken) failGeo();
		}
	}

	// ---- EFAS PNG overlay (corners TL, TR, BR, BL as lon,lat; rows resampled to Web Mercator by the pipeline)
	function failEfas() {
		efasToken++;
		removeAll(["efas-layer"], ["efas-img"]);
		showEfas = false;
		unavailable.efas = true;
	}

	$effect(() => {
		if (!map) return;
		const onError = (e) => {
			if (e.sourceId === "efas-img") failEfas();
		};
		map.on("error", onError);
		return () => map.off("error", onError);
	});

	async function updateEfas() {
		if (!map) return;
		const token = ++efasToken;
		unavailable.efas = false;
		if (!showEfas) {
			removeAll(["efas-layer"], ["efas-img"]);
			return;
		}
		const url = `${API}/efas_rp${efasRp}.png`;
		try {
			efasBounds = efasBounds || (await getJson("efas_bounds.json"));
			const head = await fetch(url, { method: "HEAD" });
			if (!head.ok) throw new Error("unavailable");
			if (token !== efasToken) return; // stale response
			const src = map.getSource("efas-img");
			if (src) {
				src.updateImage({ url, coordinates: efasBounds });
			} else {
				map.addSource("efas-img", {
					type: "image",
					url,
					coordinates: efasBounds,
				});
				addLayer({
					id: "efas-layer",
					type: "raster",
					source: "efas-img",
					paint: {
						"raster-opacity": 0.7,
						"raster-resampling": "nearest",
					},
				});
			}
		} catch {
			if (token === efasToken) failEfas();
		}
	}

	function toggleHv() {
		showHv = !showHv;
		updateHv();
	}

	function toggleGeo() {
		showGeo = !showGeo;
		updateGeo();
	}

	function toggleUnf() {
		showUnf = !showUnf;
		updateGeo();
	}

	function toggleEfas() {
		showEfas = !showEfas;
		updateEfas();
	}
</script>

{#snippet attribution(keys)}
	<p class="attrib">
		Izvor:
		{#each keys as k, i}
			{#if sources[k]}
				{i > 0 ? " · " : ""}<a
					href={sources[k].url}
					target="_blank"
					rel="noopener noreferrer">{sources[k].title}</a
				>
				— {sources[k].publisher} ({sources[k].year}), {sources[k]
					.licence}
			{/if}
		{/each}
	</p>
{/snippet}

{#snippet swatch(colour, text)}
	<li>
		<span class="sw" style="background:{colour}" aria-hidden="true"
		></span>{text}
	</li>
{/snippet}

<div class="layers">
	<div class="layer-item" class:active={showHv}>
		<div class="layer-header">
			<button
				type="button"
				class="layer-chip"
				class:active={showHv}
				aria-pressed={showHv}
				onclick={toggleHv}
			>
				<span class="chip-indicator" aria-hidden="true"></span>
				<span class="chip-title">Poplave – Hrvatske vode (2019.)</span>
			</button>

			{#if showHv}
				<label class="sel"
					>Scenarij
					<select bind:value={hvScenario} onchange={updateHv}>
						<option value="velika">Velika vjerojatnost</option>
						<option value="srednja">Srednja vjerojatnost</option>
						<option value="mala">Mala vjerojatnost</option>
					</select>
				</label>
			{/if}
		</div>

		{#if showHv}
			<div class="layer-expanded">
				{#if mapZoom < HV_MIN_ZOOM || mapZoom >= HV_MAX_ZOOM}
					<p class="hint" role="status">
						Sloj poplava vidljiv je pri zumu 12–14.
					</p>
				{/if}
				<ul class="legend">
					{#each MAP_LEGEND.hv.rows as r}{@render swatch(
							r.colour,
							r.text,
						)}{/each}
				</ul>
				<p class="hint">{MAP_LEGEND.hv.note}</p>
				{@render attribution(["flood_hv"])}
			</div>
		{/if}
	</div>

	<div class="layer-item" class:active={showGeo}>
		<div class="layer-header">
			<button
				type="button"
				class="layer-chip"
				class:active={showGeo}
				aria-pressed={showGeo}
				onclick={toggleGeo}
			>
				<span class="chip-indicator" aria-hidden="true"></span>
				<span class="chip-title"
					>Geohazardi – MPGI (2021., Banovina)</span
				>
			</button>

			{#if showGeo}
				<label class="sel"
					>Podložnost
					<select bind:value={geoLayer} onchange={updateGeo}>
						<option value="landslide">Klizišta</option>
						<option value="liquefaction">Likvefakcija</option>
						<option value="sinkhole">Vrtače</option>
					</select>
				</label>
				<button
					type="button"
					class="sub-chip"
					class:active={showUnf}
					aria-pressed={showUnf}
					onclick={toggleUnf}
				>
					<span class="sub-indicator" aria-hidden="true"></span>
					Nepovoljno za gradnju
				</button>
			{/if}
		</div>

		{#if unavailable.geo}
			<p class="hint" role="status">{MAP_UNAVAILABLE}</p>
		{/if}
		{#if showGeo}
			<div class="layer-expanded">
				<ul class="legend">
					{#each MAP_LEGEND.geo.susceptibility as r}{@render swatch(
							r.colour,
							r.text,
						)}{/each}
					{#if showUnf}{@render swatch(
							MAP_LEGEND.geo.unfavourable.colour,
							MAP_LEGEND.geo.unfavourable.text,
						)}{/if}
					{@render swatch(
						MAP_LEGEND.geo.coverage.colour,
						MAP_LEGEND.geo.coverage.text,
					)}
				</ul>
				<p class="hint">
					{MAP_LEGEND.geo.coverageNote}. {MAP_LEGEND.geo.note}
				</p>
				{@render attribution([
					geoLayer,
					...(showUnf ? ["unfavourable"] : []),
				])}
			</div>
		{/if}
	</div>

	<div class="layer-item" class:active={showEfas}>
		<div class="layer-header">
			<button
				type="button"
				class="layer-chip"
				class:active={showEfas}
				aria-pressed={showEfas}
				onclick={toggleEfas}
			>
				<span class="chip-indicator" aria-hidden="true"></span>
				<span class="chip-title">Poplave – EFAS (europski model)</span>
			</button>

			{#if showEfas}
				<label class="sel"
					>Povratno razdoblje
					<select bind:value={efasRp} onchange={updateEfas}>
						<option value="10">10 godina</option>
						<option value="100">100 godina</option>
						<option value="500">500 godina</option>
					</select>
				</label>
			{/if}
		</div>

		{#if unavailable.efas}
			<p class="hint" role="status">{MAP_UNAVAILABLE}</p>
		{/if}
		{#if showEfas}
			<div class="layer-expanded">
				<ul class="legend">
					{#each MAP_LEGEND.efas.rows as r}{@render swatch(
							r.colour,
							r.text,
						)}{/each}
				</ul>
				<p class="hint">{MAP_LEGEND.efas.note}</p>
				{@render attribution(["flood_efas"])}
			</div>
		{/if}
	</div>
</div>

<style>
	.layers {
		margin: 0.85rem 0 0;
		font-size: 0.88rem;
		border-top: 1px solid var(--rule);
	}
	.layers::before {
		content: "Slojevi karte";
		display: block;
		padding: 0.5rem 0 0.4rem;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.layer-item {
		border-bottom: 1px solid var(--hair);
		padding: 0.45rem 0 0.55rem;
		transition: background 0.12s ease;
	}
	.layer-header {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 0.85rem;
	}
	.layer-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		min-height: 2rem;
		padding: 0.25rem 0.75rem;
		font-family: var(--sans);
		font-size: 1.1rem;
		font-weight: 600;
		color: var(--ink-2);
		background: var(--surface);
		border: 1.5px solid var(--hair);
		border-radius: 4px;
		cursor: pointer;
		text-align: left;
		transition: all 0.12s ease;
	}
	.layer-chip:hover {
		background: var(--paper-2);
		border-color: var(--ink-2);
		color: var(--ink);
	}
	.layer-chip.active {
		background: var(--paper-2);
		border-color: var(--accent-ink);
		color: var(--accent-ink);
		font-weight: 700;
		box-shadow: 2px 2px 0 rgba(29, 28, 26, 0.08);
	}
	.chip-indicator {
		width: 0.65rem;
		height: 0.65rem;
		border-radius: 50%;
		border: 1.5px solid var(--muted);
		background: transparent;
		flex-shrink: 0;
		transition: all 0.12s ease;
	}
	.layer-chip.active .chip-indicator {
		background: var(--accent);
		border-color: var(--accent-ink);
		box-shadow: 0 0 0 2px rgba(176, 64, 27, 0.2);
	}
	.sub-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 1.85rem;
		padding: 0.2rem 0.6rem;
		font-family: var(--sans);
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--ink-2);
		background: var(--surface);
		border: 1px dashed var(--hair);
		border-radius: 3px;
		cursor: pointer;
		transition: all 0.12s ease;
	}
	.sub-chip:hover {
		background: var(--paper-2);
		border-color: var(--ink-2);
	}
	.sub-chip.active {
		background: var(--paper-2);
		border-style: solid;
		border-color: var(--ink);
		color: var(--ink);
		font-weight: 700;
	}
	.sub-indicator {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 2px;
		border: 1px solid var(--muted);
		background: transparent;
		flex-shrink: 0;
	}
	.sub-chip.active .sub-indicator {
		background: var(--ink);
		border-color: var(--ink);
	}
	.sel {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--ink-2);
	}
	select {
		min-height: 2rem;
		max-width: 100%;
		padding: 0.2rem 1.4rem 0.2rem 0.5rem;
		border: 1.5px solid var(--hair);
		border-radius: 3px;
		background: var(--surface);
		color: var(--ink);
		font-family: var(--sans);
		font-size: 0.82rem;
		cursor: pointer;
	}
	select:hover {
		border-color: var(--ink);
	}
	.layer-expanded {
		padding: 0.35rem 0 0 0.5rem;
		border-left: 2px solid var(--hair);
		margin: 0.4rem 0 0.2rem 0.5rem;
	}
	.legend {
		list-style: none;
		margin: 0.4rem 0 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.1rem;
		font-size: 0.82rem;
	}
	.legend li {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.sw {
		width: 1.1rem;
		height: 0.8rem;
		border: 1px solid var(--ink);
		display: inline-block;
	}
	.hint,
	.attrib {
		margin: 0.35rem 0 0;
		font-size: 0.78rem;
		color: var(--muted);
		overflow-wrap: anywhere;
	}
	button:focus-visible,
	select:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
</style>
