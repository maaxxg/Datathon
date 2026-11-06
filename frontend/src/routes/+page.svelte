<script>
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import MapLayers from '$lib/MapLayers.svelte';
	import NLQueryBox from '$lib/NLQueryBox.svelte';
	import ReportAssistant from '$lib/ReportAssistant.svelte';
	import { HAZARD_META, LEVEL_META, FLOOD_DEPTH_TEXT, PRESET_LOCATIONS, fmt, dms } from '$lib/labels.js';

	let searchQuery = $state('');
	let suggestions = $state([]);
	let geocoderAvailable = $state(true);
	let showSuggestions = $state(false);
	let selectedLabel = $state('Petrinja');
	let lat = $state(45.4375);
	let lon = $state(16.2739);

	let report = $state(null);
	let loading = $state(false);
	let errorMsg = $state('');
	let requestedLayer = $state(null);
	let activeH3Tier = $state('base');
	let layerSeq = 0;

	let availableHazards = $derived(
		report && Array.isArray(report.hazards)
			? report.hazards.filter((h) => h.level !== 'nema_podataka')
			: []
	);

	let noDataHazards = $derived(
		report && Array.isArray(report.hazards)
			? report.hazards.filter((h) => h.level === 'nema_podataka')
			: []
	);

	let mapObj = $state(null);

	let mapContainer;
	let map;
	let marker;
	let debounceTimer;

	// Only the most recent fetchReport call may change report/errorMsg/loading.
	let reqId = 0;

	async function fetchReport(targetLat, targetLon, labelText = '', flyToPoint = true) {
		const id = ++reqId;
		lat = Number(targetLat.toFixed(5));
		lon = Number(targetLon.toFixed(5));
		if (labelText) {
			selectedLabel = labelText;
		}
		loading = true;
		errorMsg = '';
		if (map && marker) {
			marker.setLngLat([lon, lat]);
			if (flyToPoint) {
				map.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 13), essential: true });
			}
		}
		try {
			const res = await fetch(`/api/report?lat=${lat}&lon=${lon}`);
			if (id !== reqId) return;
			if (!res.ok) {
				const body = await res.json().catch(() => ({}));
				if (id !== reqId) return;
				if (Array.isArray(body.detail)) throw new Error('Neispravna lokacija.');
				throw new Error(
					typeof body.detail === 'string' && body.detail
						? body.detail
						: `Greška poslužitelja (${res.status})`
				);
			}
			const data = await res.json();
			if (id !== reqId) return;
			report = data;
		} catch (err) {
			if (id !== reqId) return;
			errorMsg = err.message || 'Nije moguće dohvatiti izvještaj.';
		} finally {
			if (id === reqId) loading = false;
		}
	}

	function onSearchInput(e) {
		searchQuery = e.target.value;
		clearTimeout(debounceTimer);
		if (searchQuery.trim().length < 2) {
			suggestions = [];
			showSuggestions = false;
			return;
		}
		debounceTimer = setTimeout(async () => {
			try {
				const res = await fetch(`/api/addresses?q=${encodeURIComponent(searchQuery)}&limit=8`);
				if (!res.ok) {
					geocoderAvailable = false;
					return;
				}
				const data = await res.json();
				geocoderAvailable = data.available !== false;
				suggestions = data.results || [];
				showSuggestions = suggestions.length > 0;
			} catch {
				suggestions = [];
				showSuggestions = false;
				geocoderAvailable = false;
			}
		}, 200);
	}

	function selectAddress(item) {
		searchQuery = item.label;
		showSuggestions = false;
		fetchReport(item.lat, item.lon, item.label);
	}

	function selectPreset(preset) {
		searchQuery = preset.name;
		showSuggestions = false;
		fetchReport(preset.lat, preset.lon, preset.name);
	}

	function handleSelectRegion(center, regionName) {
		if (!center) return;
		const label = regionName
			? `Područje: ${regionName.charAt(0).toUpperCase() + regionName.slice(1)}`
			: 'Odabrano područje';
		const hasGrid = Boolean(map && map.getSource('nl-search-grid'));
		fetchReport(center.lat, center.lon, label, false);
		if (map && center.zoom && !hasGrid) {
			map.flyTo({ center: [center.lon, center.lat], zoom: center.zoom, essential: true });
		}
	}

	function getH3TierForZoom(zoom) {
		if (zoom < 11.2) return 'coarse';
		if (zoom < 12.6) return 'medium';
		if (zoom < 14.1) return 'base';
		return 'fine';
	}

	function syncH3TierFilter(force = false) {
		if (!map) return;
		const nextTier = getH3TierForZoom(map.getZoom());
		if (!force && nextTier === activeH3Tier) return;
		activeH3Tier = nextTier;
		const tierFilter = ['==', ['get', 'tier'], nextTier];
		if (map.getLayer('nl-search-grid-fill')) {
			map.setFilter('nl-search-grid-fill', tierFilter);
		}
		if (map.getLayer('nl-search-grid-line')) {
			map.setFilter('nl-search-grid-line', tierFilter);
		}
	}

	function handleUpdateSearchGrid(gridGeoJson, options = {}) {
		if (!map) return;
		const sourceId = 'nl-search-grid';
		const fillLayerId = 'nl-search-grid-fill';
		const lineLayerId = 'nl-search-grid-line';

		if (!gridGeoJson || !Array.isArray(gridGeoJson.features) || gridGeoJson.features.length === 0) {
			if (map.getLayer(lineLayerId)) map.removeLayer(lineLayerId);
			if (map.getLayer(fillLayerId)) map.removeLayer(fillLayerId);
			if (map.getSource(sourceId)) map.removeSource(sourceId);
			return;
		}

		const showExcluded = options.showExcluded !== false;
		const filteredFeatures = showExcluded
			? gridGeoJson.features
			: gridGeoJson.features.filter((f) => f.properties && f.properties.matched);

		const displayCollection = {
			type: 'FeatureCollection',
			features: filteredFeatures
		};

		activeH3Tier = getH3TierForZoom(map.getZoom());
		const tierFilter = ['==', ['get', 'tier'], activeH3Tier];

		const existingSource = map.getSource(sourceId);
		if (existingSource) {
			existingSource.setData(displayCollection);
			syncH3TierFilter(true);
		} else {
			map.addSource(sourceId, {
				type: 'geojson',
				data: displayCollection
			});
			map.addLayer({
				id: fillLayerId,
				type: 'fill',
				source: sourceId,
				filter: tierFilter,
				paint: {
					'fill-color': [
						'case',
						['boolean', ['get', 'matched'], false],
						'#4d6b22',
						'#9e2a14'
					],
					'fill-opacity': [
						'case',
						['boolean', ['get', 'matched'], false],
						0.36,
						0.16
					]
				}
			});
			map.addLayer({
				id: lineLayerId,
				type: 'line',
				source: sourceId,
				filter: tierFilter,
				paint: {
					'line-color': [
						'case',
						['boolean', ['get', 'matched'], false],
						'#3a5219',
						'#7d200f'
					],
					'line-width': [
						'case',
						['boolean', ['get', 'matched'], false],
						1.6,
						0.8
					],
					'line-opacity': 0.85
				}
			});
		}

		if (options.fitBounds && gridGeoJson.summary && Array.isArray(gridGeoJson.summary.bbox)) {
			const [w, s, e, n] = gridGeoJson.summary.bbox;
			if (w < e && s < n) {
				map.fitBounds(
					[
						[w, s],
						[e, n]
					],
					{ padding: 48, maxZoom: 13.5, duration: 900 }
				);
			}
		}
	}

	function handleActivateLayer(layerKey) {
		requestedLayer = { key: layerKey, seq: ++layerSeq };
	}

	async function handleSearchLocationText(locText) {
		searchQuery = locText;
		try {
			const res = await fetch(`/api/addresses?q=${encodeURIComponent(locText)}&limit=5`);
			if (res.ok) {
				const data = await res.json();
				if (data.results && data.results.length > 0) {
					selectAddress(data.results[0]);
					return;
				}
			}
		} catch {
			/* fallback to preset match */
		}
		const lower = locText.toLowerCase();
		const match = PRESET_LOCATIONS.find((p) => lower.includes(p.name.toLowerCase()));
		if (match) selectPreset(match);
	}

	onMount(() => {
		map = new maplibregl.Map({
			container: mapContainer,
			style: {
				version: 8,
				sources: {
					osm: {
						type: 'raster',
						tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
						tileSize: 256,
						attribution:
							'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>'
					}
				},
				layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
			},
			center: [lon, lat],
			zoom: 12
		});
		map.addControl(new maplibregl.NavigationControl(), 'top-right');

		marker = new maplibregl.Marker({ color: '#b0401b' }).setLngLat([lon, lat]).addTo(map);
		const markerEl = marker.getElement();
		markerEl.setAttribute('role', 'img');
		markerEl.setAttribute('aria-label', 'Odabrana lokacija');

		map.on('click', (e) => {
			const cLat = e.lngLat.lat;
			const cLon = e.lngLat.lng;
			fetchReport(cLat, cLon, `Odabrana točka na karti (${fmt(cLat, 4)}; ${fmt(cLon, 4)})`);
		});

		map.on('zoom', () => {
			syncH3TierFilter(false);
		});

		map.once('style.load', () => {
			mapObj = map;
		});

		fetchReport(lat, lon, selectedLabel);
	});
</script>

<section class="hero no-print" aria-label="Pretraga lokacije">
	<div class="hero-copy">
		<p class="label">List 01 — Izvještaj po lokaciji</p>
		<h1>Provjerite izloženost lokacije poplavama, potresu i geohazardima</h1>
		<p class="hero-lede">
			Unesite adresu u Hrvatskoj (iz službenog registra DGU Adrese INSPIRE), kliknite na kartu ili pretražujte područja prirodnim jezikom.
		</p>
	</div>

	<div class="search-box-wrap">
		<label for="address-input" class="label search-label">Adresa ili naselje</label>
		<div class="search-input-row">
			<div class="input-anchor">
			<input
				id="address-input"
				class="field field-lg"
				type="search"
				placeholder="Ulica, kućni broj, naselje"
				value={searchQuery}
				oninput={onSearchInput}
				onkeydown={(e) => {
					if (e.key === 'Escape') showSuggestions = false;
				}}
				onfocus={() => (showSuggestions = suggestions.length > 0)}
				autocomplete="off"
			/>
				{#if showSuggestions && suggestions.length > 0}
					<ul class="suggestions-list" aria-label="Predložene adrese">
						{#each suggestions as item}
							<li>
								<button
									type="button"
									onclick={() => selectAddress(item)}
									onkeydown={(e) => {
										if (e.key === 'Escape') showSuggestions = false;
									}}
								>
									<span>{item.label}</span>
									<span class="sugg-coords">{fmt(item.lat, 4)}; {fmt(item.lon, 4)}</span>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
			<button
				type="button"
				class="btn btn-ghost"
				disabled={loading || !report || !!errorMsg}
				onclick={() => window.print()}
			>
				<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
					<path d="M5 7V2h10v5M5 15H2V8h16v7h-3M5 12h10v6H5z" fill="none" stroke="currentColor" stroke-width="1.6" />
				</svg>
				Ispis / PDF
			</button>
		</div>

		{#if !geocoderAvailable}
			<p class="geocoder-msg" role="status">
				Pretraga adresa trenutačno nije dostupna. Odaberite lokaciju klikom na kartu.
			</p>
		{/if}



		<div class="preset-bar">
			<span class="preset-title">Testne lokacije:</span>
			<div class="preset-chips">
				{#each PRESET_LOCATIONS as p}
					<button type="button" class="preset" onclick={() => selectPreset(p)}>
						{p.name}
					</button>
				{/each}
			</div>
		</div>
	</div>
</section>

<NLQueryBox
	onSelectRegion={handleSelectRegion}
	onActivateLayer={handleActivateLayer}
	onSearchLocationText={handleSearchLocationText}
	onUpdateSearchGrid={handleUpdateSearchGrid}
	{activeH3Tier}
/>

<div class="workspace-grid">
	<section class="map-column no-print" aria-label="Interaktivna karta">
		<div class="map-sheet">
			<div class="map-frame" bind:this={mapContainer}></div>
		</div>
		<div class="map-caption">
			<span>Kliknite bilo gdje na kartu unutar Republike Hrvatske za izvještaj za tu točku.</span>
			<span class="map-caption-coords">{dms(lat, 'N', 'S')} · {dms(lon, 'E', 'W')}</span>
		</div>
		<MapLayers map={mapObj} {requestedLayer} />
	</section>

	<section class="report-column" aria-live="polite">
		<div class="print-header only-print" aria-hidden="true">
			<div class="print-meta-row">
				<span>REPUBLIKA HRVATSKA · OTVORENI PODACI JAVNOG SEKTORA</span>
				<span>WGS84 / EPSG:4326</span>
			</div>
			<div class="print-brand-row">
				<strong class="print-doc-title">Geo-rizik — Sažetak procjene prirodnih opasnosti</strong>
				<span class="print-doc-date">Datum: {new Date().toLocaleDateString('hr-HR')}</span>
			</div>
		</div>

		<header class="location-head">
			<p class="label">Izvještaj za odabranu lokaciju</p>
			<h2>{selectedLabel}</h2>
			<p class="coords">
				<span class="coords-dms">{dms(lat, 'N', 'S')}&ensp;{dms(lon, 'E', 'W')}</span>
				<span class="coords-dec">WGS84 <code>{fmt(lat, 5)}; {fmt(lon, 5)}</code></span>
			</p>
		</header>

		{#if loading}
			<div class="status-line" role="status">
				<span class="status-bar" aria-hidden="true"></span>
				Učitavanje izvještaja iz javnih servisa…
			</div>
		{:else if errorMsg}
			<div class="status-error" role="alert">
				<strong>Greška:</strong> {errorMsg}
			</div>
		{:else if report}
			{@const top = report.most_significant}
			{#if top}
				{@const topMeta = LEVEL_META[top.level] || LEVEL_META.nema_podataka}
				{@const topHazard = HAZARD_META[top.hazard] || { title: top.hazard, code: '··' }}
				<div class="verdict tone-{topMeta.tone}">
					<div class="verdict-strip">
						<span class="lvl-text">{topMeta.label}</span>
						<span class="verdict-tag">Najznačajniji utvrđeni rizik</span>
					</div>
					<div class="verdict-body">
						<div class="verdict-title">
							<span class="hz-code">{topHazard.code}</span>
							<h3>{topHazard.title}</h3>
							<span class="meter meter-{topMeta.tone}" aria-hidden="true"><i></i><i></i><i></i><i></i></span>
						</div>
						{#if report.summary}
							<p>{report.summary}</p>
						{/if}
					</div>
				</div>
			{:else if report.all_no_data}
				<div class="verdict tone-nodata">
					<div class="verdict-strip">
						<span>Nema podataka za ovu lokaciju</span>
					</div>
					{#if report.summary}
						<div class="verdict-body"><p>{report.summary}</p></div>
					{/if}
				</div>
			{:else}
				<div class="verdict tone-none">
					<div class="verdict-strip">
						<span>Nema utvrđene povišene opasnosti</span>
					</div>
					<div class="verdict-body">
						<div class="verdict-title">
							<h3>Prema dostupnim kartama nije utvrđen povišeni rizik</h3>
						</div>
						{#if report.summary}
							<p>{report.summary}</p>
						{/if}
					</div>
				</div>
			{/if}

			{#if availableHazards.length > 0}
				<div class="section-head">
					<h3>Utvrđene razine po vrstama opasnosti</h3>
					<span class="section-count">{String(availableHazards.length).padStart(2, '0')}</span>
				</div>
				<p class="section-sub">Detaljna procjena iz dostupnih izvora za odabranu točku</p>
				<ol class="ledger">
					{#each availableHazards as h}
						{@const meta = HAZARD_META[h.hazard] || { title: h.hazard, subtitle: '', code: '··' }}
						{@const lvl = LEVEL_META[h.level] || LEVEL_META.nema_podataka}
						<li class="ledger-row">
							<article>
								<div class="row-top">
									<span class="hz-code">{meta.code}</span>
									<div class="row-title">
										<h4>{meta.title}</h4>
										{#if meta.subtitle}
											<p class="row-sub">{meta.subtitle}</p>
										{/if}
									</div>
									<div class="row-level level-{lvl.tone}">
										<span class="meter meter-{lvl.tone}" aria-hidden="true"><i></i><i></i><i></i><i></i></span>
										<span class="lvl-text">{lvl.label}</span>
									</div>
								</div>

								<div class="row-body">
									{#if h.explanation}
										<p class="row-explanation">{h.explanation}</p>
									{/if}

									{#if h.detail && h.hazard === 'flood' && h.level !== 'nema_podataka' && h.detail.velika !== undefined}
										<dl class="detail-grid">
											<div>
												<dt>Velika vjerojatnost</dt>
												<dd>{FLOOD_DEPTH_TEXT[h.detail.velika] || h.detail.velika || 'nema podatka'}</dd>
											</div>
											<div>
												<dt>Srednja vjerojatnost</dt>
												<dd>{FLOOD_DEPTH_TEXT[h.detail.srednja] || h.detail.srednja || 'nema podatka'}</dd>
											</div>
											<div>
												<dt>Mala vjerojatnost</dt>
												<dd>{FLOOD_DEPTH_TEXT[h.detail.mala] || h.detail.mala || 'nema podatka'}</dd>
											</div>
										</dl>
									{:else if h.detail && h.hazard === 'flood' && h.detail.rp10 !== undefined}
										<dl class="detail-grid">
											{#each [['10', h.detail.rp10], ['100', h.detail.rp100], ['500', h.detail.rp500]] as [rp, val]}
												<div>
													<dt>Povratno razdoblje {rp} god.</dt>
													<dd>{val === null || val === undefined ? 'nema podatka' : `${fmt(val)} m`}</dd>
												</div>
											{/each}
										</dl>
									{:else if h.detail && h.hazard === 'seismic' && h.detail.ag_g !== undefined}
										<dl class="detail-grid">
											<div>
												<dt>Vršno ubrzanje tla (ag, 475 god.)</dt>
												<dd><strong>{fmt(h.detail.ag_g)} g</strong></dd>
											</div>
											{#if h.detail.udaljenost_km !== undefined && h.detail.udaljenost_km !== null}
												<div>
													<dt>Udaljenost do točke mreže</dt>
													<dd>{fmt(h.detail.udaljenost_km)} km</dd>
												</div>
											{/if}
										</dl>
									{:else if h.detail && h.detail.podloznost}
										<dl class="detail-grid">
											<div>
												<dt>Razred podložnosti u studiji</dt>
												<dd><strong>{h.detail.podloznost}</strong></dd>
											</div>
										</dl>
									{:else if h.detail && h.detail.dubina_do !== undefined}
										<dl class="detail-grid">
											<div>
												<dt>Dubina do podzemne vode</dt>
												<dd><strong>{fmt(h.detail.dubina_do)} m</strong></dd>
											</div>
											{#if h.detail.udaljenost_m !== undefined && h.detail.udaljenost_m !== null}
												<div>
													<dt>Udaljenost bušotine</dt>
													<dd>{fmt(h.detail.udaljenost_m)} m</dd>
												</div>
											{/if}
										</dl>
									{/if}

									{#if h.notes && h.notes.length > 0}
										<ul class="row-notes">
											{#each h.notes as note}
												<li>{note}</li>
											{/each}
										</ul>
									{/if}

									{#if h.source && h.source.title}
										<footer class="row-source">
											<span>
												<span class="src-key">Izvor</span>
												{[h.source.title, h.source.publisher].filter(Boolean).join(' — ')}
												{#if h.source.year || h.source.resolution}
													({[h.source.year, h.source.resolution && `rezolucija: ${h.source.resolution}`]
														.filter(Boolean)
														.join(', ')})
												{/if}
											</span>
											{#if h.source.licence}<span><span class="src-key">Licenca</span> {h.source.licence}</span>{/if}
											{#if h.source.url && h.source.url !== 'TBD'}
												<a href={h.source.url} target="_blank" rel="noopener noreferrer">Poveznica na izvor ↗</a>
											{/if}
											{#if h.source.note}
												<span class="source-note">{h.source.note}</span>
											{/if}
										</footer>
									{/if}
								</div>
							</article>
						</li>
					{/each}
				</ol>
			{/if}

			{#snippet nodataListContent()}
				<p class="nodata-subtitle">
					Izvor podataka ne pokriva ovu točku ili je servis privremeno nedostupan.
				</p>
				<ul class="nodata-list">
					{#each noDataHazards as h}
						{@const meta = HAZARD_META[h.hazard] || { title: h.hazard, code: '··' }}
						{@const reasonText =
							h.notes && h.notes.length > 0 ? h.notes.join(' ') : h.explanation || ''}
						<li class="nodata-item">
							<span class="hz-code hz-code-muted">{meta.code}</span>
							<div class="nodata-main">
								<span class="nodata-name">{meta.title}</span>
								{#if reasonText}
									<p class="nodata-reason">{reasonText}</p>
								{/if}
								{#if h.source && h.source.title}
									<span class="nodata-source">
										Izvor: {[h.source.title, h.source.publisher].filter(Boolean).join(' — ')}
										{#if h.source.year}({h.source.year}.){/if}
									</span>
								{/if}
							</div>
							<span class="nodata-tag">Nema podataka</span>
						</li>
					{/each}
				</ul>
			{/snippet}

			{#if noDataHazards.length > 0}
				<!-- Na ekranu: interaktivni sklopivi detalji -->
				<details class="nodata-box no-print" open={availableHazards.length === 0}>
					<summary>
						<span class="nodata-title">Nedostupni podaci za ovu lokaciju</span>
						<span class="section-count">{String(noDataHazards.length).padStart(2, '0')}</span>
					</summary>
					{@render nodataListContent()}
				</details>

				<!-- Za ispis / PDF (A4): uvijek otvorena lista sa sažetim popisom u istom formatu -->
				<section class="nodata-box nodata-print-box only-print" aria-label="Nedostupni podaci za ovu lokaciju">
					<div class="nodata-print-head">
						<span class="nodata-title">Nedostupni podaci za ovu lokaciju</span>
						<span class="section-count">{String(noDataHazards.length).padStart(2, '0')}</span>
					</div>
					{@render nodataListContent()}
				</section>
			{/if}

			<ReportAssistant {report} />

			{#if report.recommended_actions && report.recommended_actions.length > 0}
				<section class="actions-section" aria-label="Preporučeni koraci">
					<div class="section-head">
						<h3>Preporučeni sljedeći koraci i nadležne institucije</h3>
					</div>
					<ol class="actions-list">
						{#each report.recommended_actions as act, i}
							<li>
								<span class="action-num" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
								<div>
									<h4>{act.title}</h4>
									<p>{act.description}</p>
									<a href={act.url} target="_blank" rel="noopener noreferrer">
										{act.institution} ↗
									</a>
								</div>
							</li>
						{/each}
					</ol>
				</section>
			{/if}

			<div class="report-disclaimer" role="note">
				<strong>Napomena o odgovornosti:</strong> {report.disclaimer}
			</div>
		{/if}
	</section>
</div>

<style>
	/* ---------- Hero / search ---------- */
	.hero {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1.25rem 3rem;
		padding-bottom: 1.5rem;
		margin-bottom: 1.25rem;
		border-bottom: 1px solid var(--rule);
	}
	@media (min-width: 1100px) {
		.hero {
			grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
			align-items: end;
		}
	}
	.hero-copy .label {
		margin: 0 0 0.6rem 0;
		color: var(--accent-ink);
	}
	.hero h1 {
		margin: 0;
		font-size: clamp(1.7rem, 1.1rem + 2vw, 2.6rem);
		line-height: 1.08;
		max-width: 20ch;
		text-wrap: balance;
	}
	.hero-lede {
		margin: 0.85rem 0 0 0;
		max-width: 56ch;
		color: var(--ink-2);
		font-size: 1rem;
	}
	.search-box-wrap {
		position: relative;
	}
	.search-label {
		display: block;
		margin-bottom: 0.35rem;
	}
	.search-input-row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.input-anchor {
		position: relative;
		flex: 1;
		min-width: 240px;
	}
	.field-lg {
		min-height: 3.1rem;
		font-size: 1.08rem;
		border-width: 2px;
	}
	.search-input-row .btn {
		min-height: 3.1rem;
	}
	.suggestions-list {
		position: absolute;
		z-index: 30;
		top: 100%;
		left: 0;
		right: 0;
		margin: 0;
		padding: 0;
		list-style: none;
		background: var(--surface);
		border: 2px solid var(--ink);
		border-top-width: 0;
		box-shadow: 6px 6px 0 rgba(29, 28, 26, 0.12);
		max-height: 300px;
		overflow-y: auto;
	}
	.suggestions-list button {
		width: 100%;
		text-align: left;
		padding: 0.6rem 0.85rem;
		border: none;
		border-bottom: 1px solid var(--hair);
		background: transparent;
		color: var(--ink);
		cursor: pointer;
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		font-family: var(--sans);
		font-size: 0.95rem;
	}
	.suggestions-list button:hover,
	.suggestions-list button:focus-visible {
		background: var(--paper-2);
	}
	.sugg-coords {
		font-family: var(--mono);
		font-size: 0.78rem;
		color: var(--muted);
		white-space: nowrap;
	}
	.preset-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.45rem 0.75rem;
		margin-top: 0.85rem;
	}
	.preset-title {
		font-family: var(--sans);
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--muted);
		white-space: nowrap;
	}
	.preset-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.preset {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		min-height: 1.85rem;
		padding: 0.2rem 0.65rem;
		font-family: var(--sans);
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--ink-2);
		background: var(--surface);
		border: 1px dashed #8c826e;
		border-radius: 2px;
		cursor: pointer;
		transition: all 0.12s ease;
		white-space: nowrap;
	}
	.preset::before {
		content: '⌖';
		font-size: 0.85rem;
		color: var(--accent);
		line-height: 1;
	}
	.preset:hover {
		background: var(--paper-2);
		border-style: solid;
		border-color: var(--accent-ink);
		color: var(--accent-ink);
		box-shadow: 2px 2px 0 rgba(29, 28, 26, 0.08);
	}
	.geocoder-msg {
		margin: 0.5rem 0 0 0;
		font-size: 0.88rem;
		color: var(--muted);
	}

	/* ---------- Workspace ---------- */
	.workspace-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 2rem;
		margin-top: 1.5rem;
	}
	@media (min-width: 992px) {
		.workspace-grid {
			grid-template-columns: minmax(0, 1.25fr) minmax(400px, 1fr);
			align-items: start;
		}
	}
	@media (min-width: 992px) {
		.map-column {
			position: sticky;
			top: 1rem;
			max-height: calc(100vh - 2rem);
			overflow-y: auto;
			scrollbar-width: thin;
			padding-right: 0.25rem;
		}
	}
	.report-column {
		min-width: 0;
	}

	/* Map sheet with graduated neatline, like a printed topographic sheet */
	.map-sheet {
		--tick: 28px;
		position: relative;
		padding: 7px;
		border: 1.5px solid var(--ink);
		background:
			repeating-linear-gradient(90deg, var(--ink) 0 var(--tick), var(--surface) var(--tick) calc(var(--tick) * 2)) top / 100% 5px no-repeat,
			repeating-linear-gradient(90deg, var(--ink) 0 var(--tick), var(--surface) var(--tick) calc(var(--tick) * 2)) bottom / 100% 5px no-repeat,
			repeating-linear-gradient(180deg, var(--ink) 0 var(--tick), var(--surface) var(--tick) calc(var(--tick) * 2)) left / 5px 100% no-repeat,
			repeating-linear-gradient(180deg, var(--ink) 0 var(--tick), var(--surface) var(--tick) calc(var(--tick) * 2)) right / 5px 100% no-repeat,
			var(--surface);
	}
	.map-frame {
		width: 100%;
		height: clamp(420px, 58vh, 600px);
		min-height: 420px;
		border: 1px solid var(--ink);
	}
	@media (max-width: 768px) {
		.map-frame {
			height: 400px;
			min-height: 340px;
		}
	}
	.map-caption {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.25rem 1rem;
		margin: 0.45rem 0 0.25rem 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.map-caption-coords {
		font-family: var(--mono);
		font-size: 0.78rem;
		color: var(--ink-2);
	}

	/* ---------- Report ---------- */
	.location-head {
		padding-bottom: 0.9rem;
		margin-bottom: 1.1rem;
		border-bottom: 1px solid var(--rule);
	}
	.location-head .label {
		margin: 0;
	}
	.location-head h2 {
		margin: 0.3rem 0 0.4rem 0;
		font-size: clamp(1.45rem, 1.1rem + 1vw, 1.9rem);
		overflow-wrap: anywhere;
	}
	.coords {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 1.25rem;
		margin: 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.coords-dms {
		font-family: var(--mono);
		color: var(--ink);
	}
	.coords-dec code {
		color: var(--ink-2);
	}

	.status-line {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding: 1rem 0;
		color: var(--ink-2);
		font-size: 0.95rem;
	}
	.status-bar {
		display: block;
		height: 4px;
		background: repeating-linear-gradient(90deg, var(--ink) 0 14px, transparent 14px 28px);
		background-size: 28px 4px;
		animation: march 0.8s linear infinite;
	}
	@keyframes march {
		to {
			background-position: 28px 0;
		}
	}
	.status-error {
		padding: 0.9rem 1rem;
		background: var(--high-bg);
		border: 1.5px solid var(--high-border);
		color: var(--high-text);
	}

	/* Verdict: the most significant risk, set like a stamped heading */
	.verdict {
		border: 1.5px solid var(--ink);
		background: var(--surface);
		margin-bottom: 1.6rem;
	}
	.verdict-strip {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.25rem 1rem;
		padding: 0.5rem 1rem;
		font-weight: 700;
		font-size: 0.95rem;
		color: #fffaf0;
	}
	.verdict-tag {
		font-family: var(--mono);
		font-weight: 400;
		font-size: 0.74rem;
		letter-spacing: 0.04em;
		opacity: 0.92;
	}
	.tone-high .verdict-strip {
		background: var(--high-solid);
	}
	.tone-med .verdict-strip {
		background: var(--med-solid);
	}
	.tone-low .verdict-strip {
		background: var(--low-solid);
	}
	.tone-none .verdict-strip {
		background: var(--none-solid);
	}
	.tone-nodata .verdict-strip {
		background: var(--nodata-solid);
	}
	.verdict-body {
		padding: 0.95rem 1rem 1.05rem;
	}
	.verdict-title {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		margin-bottom: 0.45rem;
	}
	.verdict-title h3 {
		margin: 0;
		font-size: 1.4rem;
		flex: 1;
	}
	.verdict-body p {
		margin: 0;
		font-size: 0.97rem;
		color: var(--ink-2);
		max-width: 65ch;
	}

	.lvl-text {
		display: inline-block;
		text-transform: lowercase;
	}
	.lvl-text::first-letter {
		text-transform: uppercase;
	}

	.section-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
		border-bottom: 1px solid var(--rule);
		padding-bottom: 0.3rem;
	}
	.section-head h3 {
		margin: 0;
		font-size: 1.12rem;
	}
	.section-count {
		font-family: var(--mono);
		font-size: 0.85rem;
		color: var(--muted);
	}
	.section-sub {
		margin: 0.35rem 0 0 0;
		font-size: 0.84rem;
		color: var(--muted);
	}

	/* Ledger of hazards */
	.ledger {
		list-style: none;
		margin: 0.4rem 0 0 0;
		padding: 0;
	}
	.ledger-row {
		border-bottom: 1px solid var(--hair);
		padding: 1rem 0 1.05rem;
	}
	.ledger-row:last-child {
		border-bottom: 1px solid var(--rule);
	}
	.row-top {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 0.3rem 0.8rem;
		align-items: start;
	}
	@media (min-width: 560px) {
		.row-top {
			grid-template-columns: auto minmax(0, 1fr) auto;
		}
	}
	.row-title h4 {
		margin: 0;
		font-size: 1.08rem;
	}
	.row-sub {
		margin: 0.1rem 0 0 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.row-level {
		grid-column: 2;
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
		font-weight: 700;
	}
	@media (min-width: 560px) {
		.row-level {
			grid-column: auto;
			justify-content: flex-end;
			text-align: right;
			max-width: 15rem;
			padding-top: 0.2rem;
		}
	}
	.level-high {
		color: var(--high-text);
	}
	.level-med {
		color: var(--med-text);
	}
	.level-low {
		color: var(--low-text);
	}
	.level-none {
		color: var(--none-text);
	}
	.level-nodata {
		color: var(--nodata-text);
	}
	.row-body {
		padding-left: 2.9rem;
	}
	@media (max-width: 420px) {
		.row-body {
			padding-left: 0;
		}
	}
	.row-explanation {
		margin: 0.6rem 0 0 0;
		font-size: 0.95rem;
		max-width: 65ch;
	}
	.detail-grid {
		margin: 0.65rem 0 0 0;
		font-size: 0.87rem;
		display: grid;
		border-top: 1px dotted var(--hair);
	}
	.detail-grid div {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.15rem 1rem;
		padding: 0.3rem 0;
		border-bottom: 1px dotted var(--hair);
	}
	.detail-grid dt {
		color: var(--muted);
	}
	.detail-grid dd {
		margin: 0;
		font-family: var(--mono);
		font-size: 0.84rem;
		text-align: right;
	}
	.row-notes {
		margin: 0.55rem 0 0 0;
		padding-left: 1.1rem;
		font-size: 0.85rem;
		color: var(--ink-2);
	}
	.row-notes li::marker {
		content: '— ';
		color: var(--muted);
	}
	.row-source {
		margin-top: 0.65rem;
		font-size: 0.78rem;
		color: var(--muted);
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1rem;
	}
	.src-key {
		font-family: var(--mono);
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--ink-2);
		margin-right: 0.2rem;
	}
	.source-note {
		flex-basis: 100%;
	}

	/* No-data hazards */
	.nodata-box {
		margin-top: 1.4rem;
		border: 1px dashed var(--nodata-border);
		background: repeating-linear-gradient(-45deg, transparent 0 7px, rgba(122, 116, 102, 0.07) 7px 8px);
		padding: 0.2rem 0.9rem;
	}
	.nodata-box summary {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.75rem;
		padding: 0.55rem 0;
		cursor: pointer;
		list-style: none;
	}
	.nodata-box summary::-webkit-details-marker {
		display: none;
	}
	.nodata-title {
		font-weight: 700;
		font-size: 0.92rem;
	}
	.nodata-title::before {
		content: '+';
		display: inline-block;
		width: 1rem;
		font-family: var(--mono);
		color: var(--muted);
	}
	.nodata-box[open] .nodata-title::before {
		content: '−';
	}
	.nodata-subtitle {
		margin: 0 0 0.5rem 1rem;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.nodata-list {
		list-style: none;
		margin: 0 0 0.6rem 0;
		padding: 0;
	}
	.nodata-item {
		display: flex;
		align-items: flex-start;
		gap: 0.7rem;
		padding: 0.55rem 0;
		border-top: 1px solid var(--hair);
		font-size: 0.85rem;
	}
	.hz-code-muted {
		color: var(--nodata-text);
		border-style: dashed;
		background: transparent;
	}
	.nodata-main {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
		flex: 1;
	}
	.nodata-name {
		font-weight: 700;
	}
	.nodata-reason {
		margin: 0;
		font-size: 0.82rem;
		color: var(--ink-2);
	}
	.nodata-source {
		font-size: 0.76rem;
		color: var(--muted);
	}
	.nodata-tag {
		font-family: var(--mono);
		font-size: 0.7rem;
		color: var(--nodata-text);
		white-space: nowrap;
		padding-top: 0.2rem;
	}

	/* Recommended actions as a numbered procedure */
	.actions-section {
		margin-top: 2rem;
	}
	.actions-list {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.actions-list li {
		display: grid;
		grid-template-columns: 2.4rem minmax(0, 1fr);
		gap: 0.5rem;
		padding: 0.85rem 0;
		border-bottom: 1px solid var(--hair);
	}
	.action-num {
		font-family: var(--mono);
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--accent);
		line-height: 1.3;
	}
	.actions-list h4 {
		margin: 0 0 0.2rem 0;
		font-size: 1rem;
	}
	.actions-list p {
		margin: 0 0 0.3rem 0;
		font-size: 0.9rem;
		color: var(--ink-2);
	}
	.actions-list a {
		font-size: 0.88rem;
		font-weight: 600;
	}

	.report-disclaimer {
		margin-top: 1.5rem;
		padding-top: 0.75rem;
		border-top: 3px double var(--rule);
		font-size: 0.82rem;
		color: var(--muted);
	}

	.print-header {
		border-bottom: 2px solid #000;
		padding-bottom: 0.5rem;
		margin-bottom: 1.25rem;
	}
	.print-meta-row {
		display: flex;
		justify-content: space-between;
		font-family: var(--mono);
		font-size: 0.72rem;
		color: #333;
		border-bottom: 1px solid #ccc;
		padding-bottom: 0.25rem;
		margin-bottom: 0.4rem;
	}
	.print-brand-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}
	.print-doc-title {
		font-family: var(--serif);
		font-size: 1.15rem;
	}
	.print-doc-date {
		font-family: var(--mono);
		font-size: 0.76rem;
	}

	.nodata-print-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.75rem;
		padding: 0.35rem 0 0.25rem;
		border-bottom: 1px solid var(--hair);
		margin-bottom: 0.35rem;
	}

	@media print {
		.workspace-grid {
			display: block !important;
			margin: 0 !important;
			gap: 0 !important;
			width: 100% !important;
		}
		.report-column {
			width: 100% !important;
			max-width: 100% !important;
		}
		.location-head {
			padding-bottom: 0.4rem;
			margin-bottom: 0.6rem;
			break-inside: avoid;
			page-break-inside: avoid;
		}
		.location-head h2 {
			font-size: 1.35rem;
			margin: 0.15rem 0 0.25rem 0;
		}
		.verdict {
			margin-bottom: 0.8rem;
			break-inside: avoid;
			page-break-inside: avoid;
		}
		.verdict-strip {
			-webkit-print-color-adjust: exact !important;
			print-color-adjust: exact !important;
			padding: 0.35rem 0.75rem;
		}
		.verdict-body {
			padding: 0.6rem 0.75rem;
		}
		.verdict-title h3 {
			font-size: 1.15rem;
		}
		.section-head {
			padding-bottom: 0.2rem;
			margin-top: 0.8rem;
			break-after: avoid;
			page-break-after: avoid;
		}
		.ledger {
			margin-top: 0.2rem;
		}
		.ledger-row {
			padding: 0.55rem 0;
			break-inside: avoid;
			page-break-inside: avoid;
		}
		.detail-grid {
			margin-top: 0.35rem;
			padding: 0.2rem 0;
			break-inside: avoid;
			page-break-inside: avoid;
		}
		.row-source {
			margin-top: 0.35rem;
		}
		.nodata-box {
			margin-top: 0.8rem;
			padding: 0.5rem 0.75rem;
			background: #faf8f4 !important;
			border: 1px dashed var(--nodata-border) !important;
			break-inside: auto;
		}
		.nodata-item {
			padding: 0.35rem 0;
			break-inside: avoid;
			page-break-inside: avoid;
		}
		.actions-section {
			margin-top: 0.9rem;
			break-inside: avoid;
			page-break-inside: avoid;
		}
		.actions-list li {
			padding: 0.45rem 0;
			break-inside: avoid;
			page-break-inside: avoid;
		}
		.report-disclaimer {
			margin-top: 0.8rem;
			padding-top: 0.45rem;
			font-size: 0.78rem;
			break-inside: avoid;
			page-break-inside: avoid;
		}
		.meter i,
		.hz-code,
		.nodata-tag {
			-webkit-print-color-adjust: exact !important;
			print-color-adjust: exact !important;
		}
	}
</style>
