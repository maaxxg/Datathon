<script>
	import { onMount } from "svelte";
	import maplibregl from "maplibre-gl";
	import "maplibre-gl/dist/maplibre-gl.css";
	import {
		HAZARD_META,
		LEVEL_META,
		FLOOD_DEPTH_TEXT,
		PRESET_LOCATIONS,
		fmt,
	} from "$lib/labels.js";

	let searchQuery = $state("");
	let suggestions = $state([]);
	let geocoderAvailable = $state(true);
	let showSuggestions = $state(false);
	let selectedLabel = $state("Zagreb uz Savu");
	let lat = $state(45.7876);
	let lon = $state(15.9797);

	let report = $state(null);
	let loading = $state(false);
	let errorMsg = $state("");

	let showHvLayer = $state(false);
	let hvScenario = $state("srednja");
	let mapZoom = $state(12);
	// Verified 3. 11. 2026.: HV WMS renders pixels only for tile zoom 12-14.
	const HV_MIN_ZOOM = 12;
	const HV_MAX_ZOOM = 15;

	let mapContainer;
	let map;
	let marker;
	let debounceTimer;

	// Opasnosti s podacima za odabranu lokaciju vs. opasnosti bez podataka
	let availableHazards = $derived(
		report?.hazards?.filter((h) => h.level !== "nema_podataka") || [],
	);
	let noDataHazards = $derived(
		report?.hazards?.filter((h) => h.level === "nema_podataka") || [],
	);

	async function fetchReport(targetLat, targetLon, labelText = "") {
		lat = Number(targetLat.toFixed(5));
		lon = Number(targetLon.toFixed(5));
		if (labelText) {
			selectedLabel = labelText;
		}
		loading = true;
		errorMsg = "";
		if (map && marker) {
			marker.setLngLat([lon, lat]);
			map.flyTo({
				center: [lon, lat],
				zoom: Math.max(map.getZoom(), 13),
				essential: true,
			});
		}
		try {
			const res = await fetch(`/api/report?lat=${lat}&lon=${lon}`);
			if (!res.ok) {
				const body = await res.json().catch(() => ({}));
				if (Array.isArray(body.detail))
					throw new Error("Neispravna lokacija.");
				throw new Error(
					typeof body.detail === "string" && body.detail
						? body.detail
						: `Greška poslužitelja (${res.status})`,
				);
			}
			report = await res.json();
		} catch (err) {
			errorMsg = err.message || "Nije moguće dohvatiti izvještaj.";
		} finally {
			loading = false;
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
				const res = await fetch(
					`/api/addresses?q=${encodeURIComponent(searchQuery)}&limit=8`,
				);
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

	function updateWmsLayer() {
		if (!map || !map.isStyleLoaded()) return;
		const sourceId = "hv-flood-wms";
		const layerId = "hv-flood-layer";
		if (map.getLayer(layerId)) map.removeLayer(layerId);
		if (map.getSource(sourceId)) map.removeSource(sourceId);
		if (!showHvLayer) return;

		const wmsLayer = `poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-${hvScenario}-vjerojatnost_2019`;
		const tileUrl =
			`https://servisi.voda.hr/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap` +
			`&LAYERS=${wmsLayer}&STYLES=&CRS=EPSG:3857&BBOX={bbox-epsg-3857}` +
			`&WIDTH=256&HEIGHT=256&FORMAT=image/png&TRANSPARENT=true`;

		map.addSource(sourceId, {
			type: "raster",
			tiles: [tileUrl],
			tileSize: 256,
			attribution: "© Hrvatske vode (2019.)",
		});
		map.addLayer({
			id: layerId,
			type: "raster",
			source: sourceId,
			minzoom: HV_MIN_ZOOM,
			maxzoom: HV_MAX_ZOOM,
			paint: { "raster-opacity": 0.72 },
		});
	}

	onMount(() => {
		map = new maplibregl.Map({
			container: mapContainer,
			style: {
				version: 8,
				sources: {
					osm: {
						type: "raster",
						tiles: [
							"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
						],
						tileSize: 256,
						attribution:
							'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>',
					},
				},
				layers: [{ id: "osm", type: "raster", source: "osm" }],
			},
			center: [lon, lat],
			zoom: 13,
		});
		map.addControl(new maplibregl.NavigationControl(), "top-right");
		map.on("zoom", () => (mapZoom = map.getZoom()));
		mapZoom = map.getZoom();

		marker = new maplibregl.Marker({ color: "#1d4ed8" })
			.setLngLat([lon, lat])
			.addTo(map);

		map.on("click", (e) => {
			const cLat = e.lngLat.lat;
			const cLon = e.lngLat.lng;
			fetchReport(
				cLat,
				cLon,
				`Odabrana točka na karti (${fmt(cLat, 4)}; ${fmt(cLon, 4)})`,
			);
		});

		map.on("load", () => {
			updateWmsLayer();
		});

		fetchReport(lat, lon, selectedLabel);
	});
</script>

<section class="search-panel no-print" aria-label="Pretraga lokacije">
	<div class="search-header">
		<h1>
			Provjerite izloženost lokacije poplavama, potresu i geohazardima
		</h1>
		<p>
			Unesite adresu u Hrvatskoj (iz službenog registra DGU Adrese
			INSPIRE) ili kliknite izravno na kartu.
		</p>
	</div>

	<div class="search-box-wrap">
		<label for="address-input" class="sr-only"
			>Unesite adresu ili naselje</label
		>
		<div class="search-input-row">
			<input
				id="address-input"
				type="search"
				placeholder="Upišite ulicu, kućni broj i naselje..."
				value={searchQuery}
				oninput={onSearchInput}
				onkeydown={(e) => {
					if (e.key === "Escape") showSuggestions = false;
				}}
				onfocus={() => (showSuggestions = suggestions.length > 0)}
				autocomplete="off"
			/>
			<button
				type="button"
				class="btn-secondary"
				onclick={() => window.print()}
			>
				🖨️ Ispis / PDF
			</button>
		</div>

		{#if !geocoderAvailable}
			<p class="geocoder-msg" role="status">
				Pretraga adresa trenutačno nije dostupna. Odaberite lokaciju
				klikom na kartu.
			</p>
		{/if}

		{#if showSuggestions && suggestions.length > 0}
			<ul
				class="suggestions-list"
				aria-label="Predložene adrese">
				{#each suggestions as item}
					<li>
						<button
							type="button"
							onclick={() => selectAddress(item)}
						>
							<strong>{item.label}</strong>
							<span>({fmt(item.lat, 4)}; {fmt(item.lon, 4)})</span
							>
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
</section>

<div class="workspace-grid">
	<section class="map-column no-print" aria-label="Interaktivna karta">
		<div class="map-toolbar">
			<label class="layer-toggle">
				<input
					type="checkbox"
					bind:checked={showHvLayer}
					onchange={updateWmsLayer}
				/>
				<span>Prikaži WMS sloj poplava (Hrvatske vode)</span>
			</label>
			{#if showHvLayer}
				<select
					bind:value={hvScenario}
					onchange={updateWmsLayer}
					aria-label="Scenarij poplave"
				>
					<option value="velika">Velika vjerojatnost</option>
					<option value="srednja">Srednja vjerojatnost</option>
					<option value="mala">Mala vjerojatnost</option>
				</select>
			{/if}
		</div>
		{#if showHvLayer && (mapZoom < HV_MIN_ZOOM || mapZoom >= HV_MAX_ZOOM)}
			<p class="map-hint" role="status">
				Sloj poplava vidljiv je pri zumu 12–14.
			</p>
		{/if}
		<div class="map-frame" bind:this={mapContainer}></div>
		<p class="map-hint">
			Savjet: Kliknite bilo gdje na kartu unutar Republike Hrvatske za
			izračun izvještaja za tu točku.
		</p>
	</section>

	<section class="report-column" aria-live="polite">
		<div class="location-bar">
			<div>
				<span class="eyebrow">Izvještaj za lokaciju</span>
				<h2>{selectedLabel}</h2>
				<p class="coords">
					WGS84 koordinate: <code>{fmt(lat, 5)}; {fmt(lon, 5)}</code>
				</p>
			</div>
		</div>

		{#if loading}
			<div class="status-card">
				Učitavanje izvještaja iz javnih servisa...
			</div>
		{:else if errorMsg}
			<div class="status-card status-error" role="alert">
				<strong>Greška:</strong>
				{errorMsg}
			</div>
		{:else if report}
			{@const top = report.most_significant}
			{#if top}
				{@const topMeta =
					LEVEL_META[top.level] || LEVEL_META.nema_podataka}
				{@const topHazard = HAZARD_META[top.hazard] || {
					title: top.hazard,
					icon: "⚠️",
				}}
				<div class="top-risk-banner tone-{topMeta.tone}">
					<div class="top-risk-header">
						<span class="badge tone-{topMeta.tone}">
							<span aria-hidden="true">{topMeta.icon}</span>
							{topMeta.label}
						</span>
						<span class="top-risk-tag"
							>Najznačajniji utvrđeni rizik</span
						>
					</div>
					<h3>{topHazard.icon} {topHazard.title}</h3>
					{#if report.summary}
						<p>{report.summary}</p>
					{/if}
				</div>
			{:else if report.all_no_data}
				<div class="top-risk-banner tone-nodata">
					<div class="top-risk-header">
						<span class="badge tone-nodata"
							><span aria-hidden="true">—</span> NEMA PODATAKA ZA OVU
							LOKACIJU</span
						>
					</div>
					{#if report.summary}
						<p>{report.summary}</p>
					{/if}
				</div>
			{:else if report.hazards.some((x) => x.level === "nema_podataka")}
				<div class="top-risk-banner tone-none">
					<div class="top-risk-header">
						<span class="badge tone-none"
							><span aria-hidden="true">○</span> NEMA UTVRĐENE POVIŠENE
							OPASNOSTI</span
						>
					</div>
					<h3>Prema dostupnim kartama nije utvrđen povišeni rizik</h3>
					<p class="banner-extra">
						Za neke opasnosti nema podataka (vidi kartice ispod).
					</p>
					{#if report.summary}
						<p>{report.summary}</p>
					{/if}
				</div>
			{:else}
				<div class="top-risk-banner tone-none">
					<div class="top-risk-header">
						<span class="badge tone-none"
							><span aria-hidden="true">✓</span> NEMA UTVRĐENE POVIŠENE
							OPASNOSTI</span
						>
					</div>
					<h3>Prema dostupnim kartama nije utvrđen povišeni rizik</h3>
					{#if report.summary}
						<p>{report.summary}</p>
					{/if}
				</div>
			{/if}

			<div class="cards-list">
				{#if availableHazards.length > 0}
					{#each availableHazards as h}
						<HazardCard {h} />
					{/each}
				{:else}
					<div class="no-active-hazards">
						<p>
							Za ovu točku nema zabilježenih specifičnih lokalnih
							podataka o rizicima u primarnim slojevima.
						</p>
					</div>
				{/if}
			</div>
		{/if}
	</section>
</div>

{#if report}
	{#if noDataHazards.length > 0}
		<section class="bottom-section no-data-section">
			<div class="section-title-wrap">
				<h3>
					Ostali slojevi bez podataka za ovu lokaciju ({noDataHazards.length})
				</h3>
				<p class="section-desc">
					Ovi slojevi (npr. geohazardi izvan područja studije
					Banovine) nisu pokriveni za odabranu točku:
				</p>
			</div>
			<div class="bottom-cards-grid">
				{#each noDataHazards as h}
					<HazardCard {h} />
				{/each}
			</div>
		</section>
	{/if}

	{#if report.recommended_actions && report.recommended_actions.length > 0}
		<section class="actions-section" aria-label="Preporučeni koraci">
			<h3>Preporučeni sljedeći koraci i nadležne institucije</h3>
			<div class="actions-grid">
				{#each report.recommended_actions as act}
					<div class="action-card">
						<h4>{act.title}</h4>
						<p>{act.description}</p>
						<a
							href={act.url}
							target="_blank"
							rel="noopener noreferrer"
						>
							{act.institution} ↗
						</a>
					</div>
				{/each}
			</div>
		</section>
	{/if}

	<div class="report-disclaimer" role="note">
		<strong>Napomena o odgovornosti:</strong>
		{report.disclaimer}
	</div>
{/if}

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
		gap: 1.25rem;
	}
	@media (min-width: 960px) {
		.workspace-grid {
			grid-template-columns: minmax(0, 1fr) 420px;
			align-items: stretch;
		}
	}
	.map-column {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.75rem;
		padding: 0.85rem;
		position: sticky;
		top: 1rem;
	}
	.map-toolbar {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.6rem;
		font-size: 0.88rem;
	}
	.layer-toggle {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
		cursor: pointer;
	}
	.map-frame {
		width: 100%;
		height: 580px;
		min-height: 480px;
		border-radius: 0.5rem;
		border: 1px solid var(--border);
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
	.eyebrow {
		text-transform: uppercase;
		letter-spacing: 0.04em;
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--muted);
	}
	.location-bar h2 {
		margin: 0.15rem 0 0.25rem 0;
		font-size: 1.3rem;
	}
	.coords {
		margin: 0;
		font-size: 0.88rem;
		color: var(--muted);
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

	.bottom-section {
		margin-top: 1.5rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0.75rem;
		padding: 1.25rem;
	}
	.no-data-section {
		border-style: dashed;
		background: #fafbfc;
	}
	.section-title-wrap h3 {
		margin: 0 0 0.25rem 0;
		font-size: 1.15rem;
		color: var(--muted);
	}
	.section-desc {
		margin: 0 0 1rem 0;
		font-size: 0.88rem;
		color: var(--muted);
	}
	.bottom-cards-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1rem;
	}
	@media (min-width: 768px) {
		.bottom-cards-grid {
			grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
		}
	}
	.no-active-hazards {
		padding: 1rem;
		background: #f8fafc;
		border-radius: 0.5rem;
		font-size: 0.9rem;
		color: var(--muted);
		border: 1px dashed var(--border);
	}
</style>
