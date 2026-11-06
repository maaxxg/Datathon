<script>
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import MapLayers from '$lib/MapLayers.svelte';
	import NLQueryBox from '$lib/NLQueryBox.svelte';
	import ReportAssistant from '$lib/ReportAssistant.svelte';
	import { HAZARD_META, LEVEL_META, FLOOD_DEPTH_TEXT, PRESET_LOCATIONS, fmt } from '$lib/labels.js';

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

	let mapColumnEl;
	let mapColHeight = $state(0);

	let mapContainer;
	let map;
	let marker;
	let debounceTimer;

	$effect(() => {
		if (!mapColumnEl) return;
		const ro = new ResizeObserver((entries) => {
			for (const entry of entries) {
				mapColHeight = Math.round(entry.contentRect.height);
			}
		});
		ro.observe(mapColumnEl);
		return () => ro.disconnect();
	});

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
						'#16a34a',
						'#dc2626'
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
						'#15803d',
						'#b91c1c'
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

		marker = new maplibregl.Marker({ color: '#1d4ed8' }).setLngLat([lon, lat]).addTo(map);
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

<section class="search-panel no-print" aria-label="Pretraga lokacije">
	<div class="search-header">
		<h1>Provjerite izloženost lokacije poplavama, potresu i geohazardima</h1>
		<p>
			Unesite adresu u Hrvatskoj (iz službenog registra DGU Adrese INSPIRE), kliknite na kartu ili pretražujte prirodnim jezikom.
		</p>
	</div>

	<div class="search-box-wrap">
		<label for="address-input" class="sr-only">Unesite adresu ili naselje</label>
		<div class="search-input-row">
			<input
				id="address-input"
				type="search"
				placeholder="Upišite ulicu, kućni broj i naselje..."
				value={searchQuery}
				oninput={onSearchInput}
				onkeydown={(e) => {
					if (e.key === 'Escape') showSuggestions = false;
				}}
				onfocus={() => (showSuggestions = suggestions.length > 0)}
				autocomplete="off"
			/>
			<button type="button" class="btn-secondary" onclick={() => window.print()}>
				🖨️ Ispis / PDF
			</button>
		</div>

		{#if !geocoderAvailable}
			<p class="geocoder-msg" role="status">
				Pretraga adresa trenutačno nije dostupna. Odaberite lokaciju klikom na kartu.
			</p>
		{/if}

		{#if showSuggestions && suggestions.length > 0}
			<ul
				class="suggestions-list"
				aria-label="Predložene adrese"
				onkeydown={(e) => {
					if (e.key === 'Escape') showSuggestions = false;
				}}
			>
				{#each suggestions as item}
					<li>
						<button type="button" onclick={() => selectAddress(item)}>
							<strong>{item.label}</strong>
							<span>({fmt(item.lat, 4)}; {fmt(item.lon, 4)})</span>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>

	<div class="preset-bar">
		<span class="preset-title">Brzi odabir testnih lokacija:</span>
		{#each PRESET_LOCATIONS as p}
			<button type="button" class="chip" onclick={() => selectPreset(p)}>
				{p.name}
			</button>
		{/each}
	</div>

	<NLQueryBox
		onSelectRegion={handleSelectRegion}
		onActivateLayer={handleActivateLayer}
		onSearchLocationText={handleSearchLocationText}
		onUpdateSearchGrid={handleUpdateSearchGrid}
		{activeH3Tier}
	/>
</section>

<div class="workspace-grid">
	<section class="map-column no-print" aria-label="Interaktivna karta" bind:this={mapColumnEl}>
		<div class="map-frame" bind:this={mapContainer}></div>
		<MapLayers map={mapObj} {requestedLayer} />
		<p class="map-hint">
			Savjet: Kliknite bilo gdje na kartu unutar Republike Hrvatske za izračun izvještaja za tu točku.
		</p>
	</section>

	<section
		class="report-column"
		aria-live="polite"
		style={mapColHeight > 0 ? `max-height: ${mapColHeight}px; height: ${mapColHeight}px;` : ''}
	>
		<div class="location-bar">
			<div class="location-bar-header">
				<span class="eyebrow">Izvještaj za lokaciju</span>
				<span class="coords">WGS84: <code>{fmt(lat, 5)}; {fmt(lon, 5)}</code></span>
			</div>
			<h2>{selectedLabel}</h2>
		</div>

		{#if loading}
			<div class="status-card">Učitavanje izvještaja iz javnih servisa...</div>
		{:else if errorMsg}
			<div class="status-card status-error" role="alert">
				<strong>Greška:</strong> {errorMsg}
			</div>
		{:else if report}
			{@const top = report.most_significant}
			{#if top}
				{@const topMeta = LEVEL_META[top.level] || LEVEL_META.nema_podataka}
				{@const topHazard = HAZARD_META[top.hazard] || { title: top.hazard, icon: '⚠️' }}
				<div class="top-risk-banner tone-{topMeta.tone}">
					<div class="top-risk-header">
						<span class="badge tone-{topMeta.tone}">
							<span aria-hidden="true">{topMeta.icon}</span> {topMeta.label}
						</span>
						<span class="top-risk-tag">Najznačajniji utvrđeni rizik</span>
					</div>
					<h3>{topHazard.icon} {topHazard.title}</h3>
					{#if report.summary}
						<p>{report.summary}</p>
					{/if}
				</div>
			{:else if report.all_no_data}
				<div class="top-risk-banner tone-nodata">
					<div class="top-risk-header">
						<span class="badge tone-nodata"><span aria-hidden="true">—</span> NEMA PODATAKA ZA OVU LOKACIJU</span>
					</div>
					{#if report.summary}
						<p>{report.summary}</p>
					{/if}
				</div>
			{:else if report.hazards.some((x) => x.level === 'nema_podataka')}
				<div class="top-risk-banner tone-none">
					<div class="top-risk-header">
						<span class="badge tone-none"><span aria-hidden="true">○</span> NEMA UTVRĐENE POVIŠENE OPASNOSTI</span>
					</div>
					<h3>Prema dostupnim kartama nije utvrđen povišeni rizik</h3>
					<p class="banner-extra">Za neke opasnosti nema podataka (vidi kartice ispod).</p>
					{#if report.summary}
						<p>{report.summary}</p>
					{/if}
				</div>
			{:else}
				<div class="top-risk-banner tone-none">
					<div class="top-risk-header">
						<span class="badge tone-none"><span aria-hidden="true">✓</span> NEMA UTVRĐENE POVIŠENE OPASNOSTI</span>
					</div>
					<h3>Prema dostupnim kartama nije utvrđen povišeni rizik</h3>
					{#if report.summary}
						<p>{report.summary}</p>
					{/if}
				</div>
			{/if}

			{#if availableHazards.length > 0}
				<div class="cards-list">
					{#each availableHazards as h}
						{@const meta = HAZARD_META[h.hazard] || { title: h.hazard, subtitle: '', icon: 'ℹ️' }}
						{@const lvl = LEVEL_META[h.level] || LEVEL_META.nema_podataka}
						<article class="hazard-card tone-border-{lvl.tone}">
							<div class="card-top">
								<div>
									<h3><span aria-hidden="true">{meta.icon}</span> {meta.title}</h3>
									{#if meta.subtitle}
										<p class="card-sub">{meta.subtitle}</p>
									{/if}
								</div>
								<span class="badge tone-{lvl.tone}">
									<span aria-hidden="true">{lvl.icon}</span> {lvl.label}
								</span>
							</div>

							{#if h.explanation}
								<p class="card-explanation">{h.explanation}</p>
							{/if}

							{#if h.detail && h.hazard === 'flood' && h.level !== 'nema_podataka' && h.detail.velika !== undefined}
								<dl class="detail-grid">
									<div>
										<dt>Velika vjerojatnost:</dt>
										<dd>{FLOOD_DEPTH_TEXT[h.detail.velika] || h.detail.velika || 'nema podatka'}</dd>
									</div>
									<div>
										<dt>Srednja vjerojatnost:</dt>
										<dd>{FLOOD_DEPTH_TEXT[h.detail.srednja] || h.detail.srednja || 'nema podatka'}</dd>
									</div>
									<div>
										<dt>Mala vjerojatnost:</dt>
										<dd>{FLOOD_DEPTH_TEXT[h.detail.mala] || h.detail.mala || 'nema podatka'}</dd>
									</div>
								</dl>
							{:else if h.detail && h.hazard === 'flood' && h.detail.rp10 !== undefined}
								<dl class="detail-grid">
									{#each [['10', h.detail.rp10], ['100', h.detail.rp100], ['500', h.detail.rp500]] as [rp, val]}
										<div>
											<dt>Povratno razdoblje {rp} god.:</dt>
											<dd>{val === null || val === undefined ? 'nema podatka' : `${fmt(val)} m`}</dd>
										</div>
									{/each}
								</dl>
							{:else if h.detail && h.hazard === 'seismic' && h.detail.ag_g !== undefined}
								<dl class="detail-grid">
									<div>
										<dt>Vršno ubrzanje tla (ag, 475 god.):</dt>
										<dd><strong>{fmt(h.detail.ag_g)} g</strong></dd>
									</div>
									{#if h.detail.udaljenost_km !== undefined && h.detail.udaljenost_km !== null}
										<div>
											<dt>Udaljenost do točke mreže:</dt>
											<dd>{fmt(h.detail.udaljenost_km)} km</dd>
										</div>
									{/if}
								</dl>
							{:else if h.detail && h.detail.podloznost}
								<dl class="detail-grid">
									<div>
										<dt>Razred podložnosti u studiji:</dt>
										<dd><strong>{h.detail.podloznost}</strong></dd>
									</div>
								</dl>
							{:else if h.detail && h.detail.dubina_do !== undefined}
								<dl class="detail-grid">
									<div>
										<dt>Dubina do podzemne vode:</dt>
										<dd><strong>{fmt(h.detail.dubina_do)} m</strong></dd>
									</div>
									{#if h.detail.udaljenost_m !== undefined && h.detail.udaljenost_m !== null}
										<div>
											<dt>Udaljenost bušotine:</dt>
											<dd>{fmt(h.detail.udaljenost_m)} m</dd>
										</div>
									{/if}
								</dl>
							{/if}

							{#if h.notes && h.notes.length > 0}
								<ul class="card-notes">
									{#each h.notes as note}
										<li>{note}</li>
									{/each}
								</ul>
							{/if}

							{#if h.source && h.source.title}
								<footer class="card-source">
									<span>
										<strong>Izvor:</strong>
										{[h.source.title, h.source.publisher].filter(Boolean).join(' — ')}
										{#if h.source.year || h.source.resolution}
											({[h.source.year, h.source.resolution && `rezolucija: ${h.source.resolution}`]
												.filter(Boolean)
												.join(', ')})
										{/if}
									</span>
									{#if h.source.licence}<span><strong>Licenca:</strong> {h.source.licence}</span>{/if}
									{#if h.source.url && h.source.url !== 'TBD'}
										<a href={h.source.url} target="_blank" rel="noopener noreferrer">Poveznica na izvor ↗</a>
									{/if}
									{#if h.source.note}
										<span class="source-note">{h.source.note}</span>
									{/if}
								</footer>
							{/if}
						</article>
					{/each}
				</div>
			{:else}
				<div class="empty-available-card">
					<p>Za ovu točku trenutno nema utvrđenih povišenih rizika u obrađenim podacima.</p>
				</div>
			{/if}

			{#if noDataHazards.length > 0}
				<div class="nodata-compact-box">
					<div class="nodata-compact-title">
						<span>Nedostupni podaci ({noDataHazards.length})</span>
						<span class="nodata-compact-subtitle">Nema zabilježenih podataka za ovu točku</span>
					</div>
					<div class="nodata-pills">
						{#each noDataHazards as h}
							{@const meta = HAZARD_META[h.hazard] || { title: h.hazard, icon: '○' }}
							<div class="nodata-pill">
								<span class="nodata-pill-icon" aria-hidden="true">{meta.icon}</span>
								<span class="nodata-pill-name">{meta.title}</span>
								<span class="nodata-pill-tag">Nema podataka</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			<ReportAssistant {report} />

			{#if report.recommended_actions && report.recommended_actions.length > 0}
				<section class="actions-section" aria-label="Preporučeni koraci">
					<h3>Preporučeni sljedeći koraci i nadležne institucije</h3>
					<div class="actions-grid">
						{#each report.recommended_actions as act}
							<div class="action-card">
								<h4>{act.title}</h4>
								<p>{act.description}</p>
								<a href={act.url} target="_blank" rel="noopener noreferrer">
									{act.institution} ↗
								</a>
							</div>
						{/each}
					</div>
				</section>
			{/if}

			<div class="report-disclaimer" role="note">
				<strong>Napomena o odgovornosti:</strong> {report.disclaimer}
			</div>
		{/if}
	</section>
</div>

<style>
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		border: 0;
	}
	.search-panel {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.75rem;
		padding: 1.25rem;
		margin-bottom: 1.25rem;
		box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
	}
	.search-header h1 {
		margin: 0 0 0.25rem 0;
		font-size: 1.35rem;
	}
	.search-header p {
		margin: 0 0 0.85rem 0;
		color: var(--muted);
		font-size: 0.95rem;
	}
	.search-box-wrap {
		position: relative;
	}
	.search-input-row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.search-input-row input {
		flex: 1;
		min-width: 240px;
		padding: 0.7rem 0.9rem;
		font-size: 1rem;
		border: 2px solid #64748b;
		border-radius: 0.5rem;
	}
	.search-input-row input:focus {
		outline: 3px solid #93c5fd;
		border-color: var(--primary);
	}
	.btn-secondary {
		padding: 0.7rem 1rem;
		font-weight: 600;
		background: #f1f5f9;
		color: var(--text);
		border: 1px solid #64748b;
		border-radius: 0.5rem;
		cursor: pointer;
	}
	.btn-secondary:hover {
		background: #e2e8f0;
	}
	.suggestions-list {
		position: absolute;
		z-index: 30;
		top: 100%;
		left: 0;
		right: 0;
		margin: 0.25rem 0 0 0;
		padding: 0;
		list-style: none;
		background: #ffffff;
		border: 2px solid var(--primary);
		border-radius: 0.5rem;
		box-shadow: 0 10px 25px rgba(15, 23, 42, 0.15);
		max-height: 280px;
		overflow-y: auto;
	}
	.suggestions-list button {
		width: 100%;
		text-align: left;
		padding: 0.65rem 0.9rem;
		border: none;
		border-bottom: 1px solid #e2e8f0;
		background: transparent;
		cursor: pointer;
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		font-size: 0.95rem;
	}
	.suggestions-list button:hover {
		background: #eff6ff;
	}
	.preset-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.45rem;
		margin-top: 0.85rem;
	}
	.preset-title {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--muted);
	}
	.chip {
		background: #eff6ff;
		color: #1e3a8a;
		border: 1px solid #93c5fd;
		border-radius: 999px;
		padding: 0.25rem 0.7rem;
		font-size: 0.82rem;
		font-weight: 600;
		cursor: pointer;
	}
	.chip:hover {
		background: #dbeafe;
	}
	.workspace-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1.5rem;
	}
	@media (min-width: 992px) {
		.workspace-grid {
			grid-template-columns: minmax(0, 1.4fr) minmax(360px, 1fr);
			align-items: start;
		}
	}
	.map-column {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.75rem;
		padding: 0.85rem;
	}
	@media (min-width: 992px) {
		.map-column {
			position: sticky;
			top: 1rem;
		}
	}
	.report-column {
		min-width: 0;
	}
	@media (min-width: 992px) {
		.report-column {
			overflow-y: auto;
			padding-right: 0.35rem;
			scrollbar-width: thin;
			scrollbar-color: #94a3b8 #f1f5f9;
		}
		.report-column::-webkit-scrollbar {
			width: 7px;
		}
		.report-column::-webkit-scrollbar-track {
			background: #f1f5f9;
			border-radius: 4px;
		}
		.report-column::-webkit-scrollbar-thumb {
			background-color: #94a3b8;
			border-radius: 4px;
		}
		.report-column::-webkit-scrollbar-thumb:hover {
			background-color: #64748b;
		}
	}
	.map-frame {
		width: 100%;
		height: 620px;
		min-height: 500px;
		border-radius: 0.5rem;
		border: 1px solid var(--border);
	}
	@media (max-width: 768px) {
		.map-frame {
			height: 420px;
		}
	}
	.map-hint {
		margin: 0.5rem 0 0 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.location-bar {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.75rem;
		padding: 1rem 1.25rem;
		margin-bottom: 1rem;
	}
	.location-bar-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-bottom: 0.2rem;
	}
	.eyebrow {
		text-transform: uppercase;
		letter-spacing: 0.04em;
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--muted);
	}
	.location-bar h2 {
		margin: 0.15rem 0 0 0;
		font-size: 1.3rem;
	}
	.coords {
		margin: 0;
		font-size: 0.82rem;
		color: var(--muted);
		background: #f1f5f9;
		padding: 0.2rem 0.5rem;
		border-radius: 0.375rem;
		border: 1px solid #e2e8f0;
	}
	.coords code {
		font-weight: 600;
		color: #1e293b;
	}
	.top-risk-banner {
		border-radius: 0.75rem;
		padding: 1rem 1.25rem;
		margin-bottom: 1rem;
		border: 2px solid;
	}
	.top-risk-header {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.4rem;
	}
	.top-risk-tag {
		font-size: 0.8rem;
		font-weight: 700;
		text-transform: uppercase;
	}
	.top-risk-banner h3 {
		margin: 0.2rem 0 0.35rem 0;
		font-size: 1.2rem;
	}
	.top-risk-banner p {
		margin: 0;
		font-size: 0.95rem;
	}
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.25rem 0.65rem;
		border-radius: 0.375rem;
		font-size: 0.8rem;
		font-weight: 800;
		border: 1.5px solid;
	}
	.tone-high {
		background: var(--high-bg);
		border-color: var(--high-border);
		color: var(--high-text);
	}
	.tone-med {
		background: var(--med-bg);
		border-color: var(--med-border);
		color: var(--med-text);
	}
	.tone-low {
		background: var(--low-bg);
		border-color: var(--low-border);
		color: var(--low-text);
	}
	.tone-none {
		background: var(--none-bg);
		border-color: var(--none-border);
		color: var(--none-text);
	}
	.tone-nodata {
		background: var(--nodata-bg);
		border-color: var(--nodata-border);
		color: var(--nodata-text);
	}
	.cards-list {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}
	.hazard-card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-left-width: 6px;
		border-radius: 0.65rem;
		padding: 1rem 1.15rem;
	}
	.tone-border-high {
		border-left-color: var(--high-border);
	}
	.tone-border-med {
		border-left-color: var(--med-border);
	}
	.tone-border-low {
		border-left-color: var(--low-border);
	}
	.tone-border-none {
		border-left-color: var(--none-border);
	}
	.tone-border-nodata {
		border-left-color: var(--nodata-border);
	}
	.card-top {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.5rem;
	}
	.card-top h3 {
		margin: 0;
		font-size: 1.05rem;
	}
	.card-sub {
		margin: 0.15rem 0 0 0;
		font-size: 0.83rem;
		color: var(--muted);
	}
	.card-explanation {
		margin: 0.65rem 0 0 0;
		font-size: 0.94rem;
	}
	.detail-grid {
		margin: 0.65rem 0 0 0;
		padding: 0.6rem 0.75rem;
		background: #f8fafc;
		border-radius: 0.4rem;
		font-size: 0.88rem;
		display: grid;
		gap: 0.3rem;
	}
	.detail-grid div {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.detail-grid dt {
		color: var(--muted);
	}
	.detail-grid dd {
		margin: 0;
	}
	.card-notes {
		margin: 0.5rem 0 0 0;
		padding-left: 1.2rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
.geocoder-msg {
		margin: 0.5rem 0 0 0;
		font-size: 0.88rem;
		color: var(--muted);
	}
	.banner-extra {
		font-weight: 600;
		margin: 0 0 0.35rem 0 !important;
	}
	.source-note {
		flex-basis: 100%;
	}
	.card-source {
		margin-top: 0.75rem;
		padding-top: 0.55rem;
		border-top: 1px solid #e2e8f0;
		font-size: 0.8rem;
		color: var(--muted);
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.actions-section {
		margin-top: 1.25rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.75rem;
		padding: 1rem 1.25rem;
	}
	.actions-section h3 {
		margin: 0 0 0.75rem 0;
		font-size: 1.05rem;
	}
	.actions-grid {
		display: grid;
		gap: 0.75rem;
	}
	.action-card {
		padding: 0.75rem;
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 0.5rem;
	}
	.action-card h4 {
		margin: 0 0 0.25rem 0;
		font-size: 0.95rem;
	}
	.action-card p {
		margin: 0 0 0.4rem 0;
		font-size: 0.88rem;
		color: var(--muted);
	}
	.report-disclaimer {
		margin-top: 1rem;
		padding: 0.85rem 1rem;
		background: #f1f5f9;
		border: 1px solid #cbd5e1;
		border-radius: 0.5rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.status-card {
		padding: 1.25rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.75rem;
	}
	.status-error {
		background: var(--high-bg);
		border-color: var(--high-border);
		color: var(--high-text);
	}
	.empty-available-card {
		background: #f8fafc;
		border: 1px dashed var(--border);
		border-radius: 0.65rem;
		padding: 1rem;
		color: var(--muted);
		font-size: 0.92rem;
	}
	.empty-available-card p {
		margin: 0;
	}

	/* Dimmed, compact list for hazards without data on the right side */
	.nodata-compact-box {
		margin-top: 1rem;
		padding: 0.75rem 0.9rem;
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 0.65rem;
		opacity: 0.75;
		transition: opacity 0.2s ease;
	}
	.nodata-compact-box:hover {
		opacity: 1;
	}
	.nodata-compact-title {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		font-size: 0.78rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: #64748b;
	}
	.nodata-compact-subtitle {
		font-size: 0.75rem;
		font-weight: 400;
		text-transform: none;
		letter-spacing: normal;
		color: #94a3b8;
	}
	.nodata-pills {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.nodata-pill {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.35rem 0.65rem;
		background: #ffffff;
		border: 1px solid #e2e8f0;
		border-radius: 0.375rem;
		font-size: 0.82rem;
		color: #64748b;
	}
	.nodata-pill-icon {
		margin-right: 0.45rem;
		font-size: 0.85rem;
		filter: grayscale(1);
		opacity: 0.7;
	}
	.nodata-pill-name {
		font-weight: 500;
		color: #475569;
		flex: 1;
	}
	.nodata-pill-tag {
		font-size: 0.72rem;
		font-weight: 600;
		color: #94a3b8;
		background: #f1f5f9;
		padding: 0.15rem 0.45rem;
		border-radius: 0.25rem;
		letter-spacing: 0.02em;
	}
</style>
