<script>
	import { onMount } from 'svelte';
	import { MAP_LEGEND, MAP_UNAVAILABLE } from '$lib/labels.js';

	let { map } = $props();

	const HV_MIN_ZOOM = 12;
	const HV_MAX_ZOOM = 15;
	const API = '/api/map-data';
	// Bottom to top. Marker is a DOM element, always above.
	const ORDER = ['efas-layer', 'hv-flood-layer', 'geo-susc-fill', 'geo-susc-line', 'geo-unf-fill', 'geo-unf-line', 'geo-coverage-line'];

	let sources = $state({});
	let mapZoom = $state(12);

	let showHv = $state(false);
	let hvScenario = $state('srednja');
	let showGeo = $state(false);
	let geoLayer = $state('landslide');
	let showUnf = $state(false);
	let showEfas = $state(false);
	let efasRp = $state('100');
	let unavailable = $state({ geo: false, efas: false });

	let efasBounds = null;
	const geoCache = {};

	onMount(async () => {
		try {
			const res = await fetch('/api/sources');
			if (res.ok) sources = (await res.json()).layers || {};
		} catch {
			/* attribution falls back to empty; the legend still shows */
		}
	});

	$effect(() => {
		if (!map) return;
		const onZoom = () => (mapZoom = map.getZoom());
		map.on('zoom', onZoom);
		mapZoom = map.getZoom();
		return () => map.off('zoom', onZoom);
	});

	function attr(key) {
		const s = sources[key];
		return s ? `${s.publisher} (${s.year})` : '';
	}

	function beforeIdFor(id) {
		for (const next of ORDER.slice(ORDER.indexOf(id) + 1)) if (map.getLayer(next)) return next;
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
		if (!res.ok) throw new Error('unavailable');
		return (geoCache[name] = await res.json());
	}

	// ---- HV flood WMS (EPSG:3857, 256 px)
	function updateHv() {
		if (!map) return;
		removeAll(['hv-flood-layer'], ['hv-flood-wms']);
		if (!showHv) return;
		const wmsLayer = `poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-${hvScenario}-vjerojatnost_2019`;
		const tileUrl =
			`https://servisi.voda.hr/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap` +
			`&LAYERS=${wmsLayer}&STYLES=&CRS=EPSG:3857&BBOX={bbox-epsg-3857}` +
			`&WIDTH=256&HEIGHT=256&FORMAT=image/png&TRANSPARENT=true`;
		map.addSource('hv-flood-wms', {
			type: 'raster',
			tiles: [tileUrl],
			tileSize: 256,
			attribution: attr('flood_hv') ? `© ${attr('flood_hv')}` : '© Hrvatske vode'
		});
		addLayer({
			id: 'hv-flood-layer',
			type: 'raster',
			source: 'hv-flood-wms',
			minzoom: HV_MIN_ZOOM,
			maxzoom: HV_MAX_ZOOM,
			paint: { 'raster-opacity': 0.72 }
		});
	}

	// ---- MPGI geohazards (simplified GeoJSON served by our API, EPSG:4326 lon,lat)
	const GEO_LAYERS = ['geo-susc-fill', 'geo-susc-line', 'geo-unf-fill', 'geo-unf-line', 'geo-coverage-line'];
	const GEO_SOURCES = ['geo-susc', 'geo-unf', 'geo-coverage'];
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
				getJson('banovina_coverage.geojson'),
				showUnf ? getJson('geohazard_unfavourable.geojson') : null
			]);
			if (token !== geoToken) return; // stale response
			const attribution = attr(geoLayer) ? `© ${attr(geoLayer)}` : '© MPGI';
			if (map.getSource('geo-susc')) {
				map.getSource('geo-susc').setData(data);
			} else {
				map.addSource('geo-susc', { type: 'geojson', data, attribution });
				const colour = ['match', ['get', 'podloznost'], 'niska', '#facc15', 'srednja', '#f97316', 'visoka', '#b91c1c', '#6b7280'];
				addLayer({ id: 'geo-susc-fill', type: 'fill', source: 'geo-susc', paint: { 'fill-color': colour, 'fill-opacity': 0.45 } });
				addLayer({ id: 'geo-susc-line', type: 'line', source: 'geo-susc', paint: { 'line-color': colour, 'line-width': 1 } });
			}
			if (!map.getSource('geo-coverage')) {
				map.addSource('geo-coverage', { type: 'geojson', data: cov });
				addLayer({
					id: 'geo-coverage-line',
					type: 'line',
					source: 'geo-coverage',
					paint: { 'line-color': '#0f766e', 'line-width': 2, 'line-dasharray': [3, 2] }
				});
			}
			removeAll(['geo-unf-fill', 'geo-unf-line'], ['geo-unf']);
			if (unf) {
				map.addSource('geo-unf', { type: 'geojson', data: unf, attribution: attr('unfavourable') ? `© ${attr('unfavourable')}` : '© MPGI' });
				addLayer({ id: 'geo-unf-fill', type: 'fill', source: 'geo-unf', paint: { 'fill-color': '#4c1d95', 'fill-opacity': 0.35 } });
				addLayer({ id: 'geo-unf-line', type: 'line', source: 'geo-unf', paint: { 'line-color': '#4c1d95', 'line-width': 2 } });
			}
		} catch {
			if (token === geoToken) failGeo();
		}
	}

	// ---- EFAS PNG overlay (corners TL, TR, BR, BL as lon,lat; rows resampled to Web Mercator by the pipeline)
	function failEfas() {
		efasToken++;
		removeAll(['efas-layer'], ['efas-img']);
		showEfas = false;
		unavailable.efas = true;
	}

	$effect(() => {
		if (!map) return;
		const onError = (e) => {
			if (e.sourceId === 'efas-img') failEfas();
		};
		map.on('error', onError);
		return () => map.off('error', onError);
	});

	async function updateEfas() {
		if (!map) return;
		const token = ++efasToken;
		unavailable.efas = false;
		if (!showEfas) {
			removeAll(['efas-layer'], ['efas-img']);
			return;
		}
		const url = `${API}/efas_rp${efasRp}.png`;
		try {
			efasBounds = efasBounds || (await getJson('efas_bounds.json'));
			const head = await fetch(url, { method: 'HEAD' });
			if (!head.ok) throw new Error('unavailable');
			if (token !== efasToken) return; // stale response
			const src = map.getSource('efas-img');
			if (src) {
				src.updateImage({ url, coordinates: efasBounds });
			} else {
				map.addSource('efas-img', { type: 'image', url, coordinates: efasBounds });
				addLayer({ id: 'efas-layer', type: 'raster', source: 'efas-img', paint: { 'raster-opacity': 0.7, 'raster-resampling': 'nearest' } });
			}
		} catch {
			if (token === efasToken) failEfas();
		}
	}
</script>

{#snippet attribution(keys)}
	<p class="attrib">
		Izvor:
		{#each keys as k, i}
			{#if sources[k]}
				{i > 0 ? ' · ' : ''}<a href={sources[k].url} target="_blank" rel="noopener noreferrer">{sources[k].title}</a> — {sources[k].publisher} ({sources[k].year}), {sources[k].licence}
			{/if}
		{/each}
	</p>
{/snippet}

{#snippet swatch(colour, text)}
	<li><span class="sw" style="background:{colour}" aria-hidden="true"></span>{text}</li>
{/snippet}

<div class="layers">
	<fieldset class="group">
		<legend>Poplave – Hrvatske vode (2019.)</legend>
		<div class="row">
			<label class="toggle"><input type="checkbox" bind:checked={showHv} onchange={updateHv} /> Prikaži sloj</label>
			{#if showHv}
				<label class="sel">Scenarij
					<select bind:value={hvScenario} onchange={updateHv}>
						<option value="velika">Velika vjerojatnost</option>
						<option value="srednja">Srednja vjerojatnost</option>
						<option value="mala">Mala vjerojatnost</option>
					</select>
				</label>
			{/if}
		</div>
		{#if showHv}
			{#if mapZoom < HV_MIN_ZOOM || mapZoom >= HV_MAX_ZOOM}
				<p class="hint" role="status">Sloj poplava vidljiv je pri zumu 12–14.</p>
			{/if}
			<ul class="legend">{#each MAP_LEGEND.hv.rows as r}{@render swatch(r.colour, r.text)}{/each}</ul>
			<p class="hint">{MAP_LEGEND.hv.note}</p>
			{@render attribution(['flood_hv'])}
		{/if}
	</fieldset>

	<fieldset class="group">
		<legend>Geohazardi – MPGI (2021., samo Banovina)</legend>
		<div class="row">
			<label class="toggle"><input type="checkbox" bind:checked={showGeo} onchange={updateGeo} /> Prikaži sloj</label>
			{#if showGeo}
				<label class="sel">Podložnost
					<select bind:value={geoLayer} onchange={updateGeo}>
						<option value="landslide">Klizišta</option>
						<option value="liquefaction">Likvefakcija</option>
						<option value="sinkhole">Vrtače</option>
					</select>
				</label>
				<label class="toggle"><input type="checkbox" bind:checked={showUnf} onchange={updateGeo} /> Nepovoljno za gradnju</label>
			{/if}
		</div>
		{#if unavailable.geo}
			<p class="hint" role="status">{MAP_UNAVAILABLE}</p>
		{/if}
		{#if showGeo}
			<ul class="legend">
				{#each MAP_LEGEND.geo.susceptibility as r}{@render swatch(r.colour, r.text)}{/each}
				{#if showUnf}{@render swatch(MAP_LEGEND.geo.unfavourable.colour, MAP_LEGEND.geo.unfavourable.text)}{/if}
				{@render swatch(MAP_LEGEND.geo.coverage.colour, MAP_LEGEND.geo.coverage.text)}
			</ul>
			<p class="hint">{MAP_LEGEND.geo.coverageNote}. {MAP_LEGEND.geo.note}</p>
			{@render attribution([geoLayer, ...(showUnf ? ['unfavourable'] : [])])}
		{/if}
	</fieldset>

	<fieldset class="group">
		<legend>Poplave – EFAS (europski model, okvirno)</legend>
		<div class="row">
			<label class="toggle"><input type="checkbox" bind:checked={showEfas} onchange={updateEfas} /> Prikaži sloj</label>
			{#if showEfas}
				<label class="sel">Povratno razdoblje
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
			<ul class="legend">{#each MAP_LEGEND.efas.rows as r}{@render swatch(r.colour, r.text)}{/each}</ul>
			<p class="hint">{MAP_LEGEND.efas.note}</p>
			{@render attribution(['flood_efas'])}
		{/if}
	</fieldset>
</div>

<style>
	.layers {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin: 0.6rem 0;
		font-size: 0.88rem;
	}
	.group {
		margin: 0;
		min-width: 0;
		border: 1px solid var(--border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.7rem 0.6rem;
	}
	.group legend {
		font-weight: 700;
		padding: 0 0.3rem;
	}
	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 1rem;
	}
	.toggle,
	.sel {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
	}
	.toggle {
		cursor: pointer;
	}
	.legend {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 1rem;
	}
	.legend li {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}
	.sw {
		width: 1.1rem;
		height: 0.8rem;
		border: 1px solid #1f2937;
		display: inline-block;
	}
	.hint,
	.attrib {
		margin: 0.4rem 0 0;
		font-size: 0.82rem;
		color: var(--muted);
		overflow-wrap: anywhere;
	}
	/* WCAG 2.2 AA 2.5.8: tap targets >= 24 x 24 px */
	input[type='checkbox'] {
		width: 1.5rem;
		height: 1.5rem;
		margin: 0;
	}
	select {
		min-height: 2rem;
		max-width: 100%;
		padding-inline-end: 1.5rem;
	}
	.toggle,
	.sel {
		min-height: 2rem;
	}
	input:focus-visible,
	select:focus-visible {
		outline: 2px solid #1d4ed8;
		outline-offset: 2px;
	}
</style>
