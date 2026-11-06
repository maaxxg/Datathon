<script>
	import { HAZARD_META, fmt } from '$lib/labels.js';

	let {
		onSelectRegion = () => {},
		onActivateLayer = () => {},
		onSearchLocationText = () => {},
		onUpdateSearchGrid = () => {},
		activeH3Tier = 'base'
	} = $props();

	const EXAMPLE_QUERIES = [
		'Pronađi mi područja oko Petrinje bez poplava i s niskom podložnosti klizištima.',
		'Pronađi područja u Petrinji bez poplava i s cijenom kvadrata ispod 1500 eura.',
		'Pronađi područja u Splitu bez poplava i bez klizišta.',
		'Prikaži sloj klizišta na Banovini.',
		'Usporedi Ulicu Matije Gupca 12 u Petrinji s Rimskom ulicom 19 u Sisku.'
	];

	const INTENT_LABELS = {
		find_area: 'Pretraga područja (filteri opasnosti na H3 mreži)',
		compare_locations: 'Usporedba lokacija',
		show_layer: 'Prikaz sloja na karti'
	};

	const MAX_LEVEL_LABELS = {
		nema_prema_karti: 'nema prema karti (bez opasnosti)',
		vrlo_niska_seizmicnost: 'vrlo niska seizmičnost (≤ 0,04 g)',
		nisko: 'najviše nisko',
		niska_seizmicnost: 'niska seizmičnost (≤ 0,08 g)',
		srednje: 'najviše srednje',
		iznad_praga_niske_seizmicnosti: 'iznad praga niske seizmičnosti'
	};

	const LAYER_NAMES = {
		flood_hv: 'Poplave – Hrvatske vode (2019.)',
		flood_efas: 'Poplave – EFAS (europski model)',
		seismic: 'Potresna opasnost (ESHM20)',
		landslide: 'Podložnost klizištima (MPGI)',
		liquefaction: 'Podložnost likvefakciji (MPGI)',
		sinkhole: 'Podložnost vrtačama (MPGI)',
		unfavourable: 'Nepovoljno za gradnju (MPGI)',
		groundwater: 'Dubina podzemne vode (MPGI)'
	};

	let queryText = $state('');
	let loading = $state(false);
	let errorMsg = $state('');
	let result = $state(null);

	let showGridOnMap = $state(true);
	let showExcludedCells = $state(true);

	// Manual filter addition state
	let newHazard = $state('flood');
	let newMaxLevel = $state('nema_prema_karti');

	let activeGrid = $derived(result?.grid || result?.validated?.grid || null);

	function syncGridToMap(gridObj, fitBounds = false) {
		if (!gridObj || !showGridOnMap) {
			onUpdateSearchGrid(null, { showExcluded: showExcludedCells, fitBounds: false });
			return;
		}
		onUpdateSearchGrid(gridObj, { showExcluded: showExcludedCells, fitBounds });
	}

	async function submitQuery(textToRun = queryText) {
		const trimmed = (textToRun || '').trim();
		if (trimmed.length < 2) return;
		queryText = trimmed;
		loading = true;
		errorMsg = '';
		try {
			const res = await fetch('/api/query', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ text: trimmed })
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				throw new Error(err.detail || `Greška pri obradi upita (${res.status})`);
			}
			const data = await res.json();
			showGridOnMap = true;
			result = data;
			applyMapEffects(data.validated, data.grid);
		} catch (e) {
			errorMsg = e.message || 'Nije moguće obraditi upit.';
		} finally {
			loading = false;
		}
	}

	function applyMapEffects(validated, gridObj) {
		if (!validated) return;
		if (validated.center) {
			onSelectRegion(validated.center, validated.region);
		}
		if (validated.intent === 'show_layer' && validated.layer) {
			onActivateLayer(validated.layer);
			syncGridToMap(null, false);
			return;
		}
		syncGridToMap(gridObj || validated.grid || null, true);
	}

	async function revalidateParsed(updatedParsed) {
		try {
			const res = await fetch('/api/query/validate', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(updatedParsed)
			});
			if (!res.ok) return;
			const validated = await res.json();
			const nextGrid = validated.grid || null;
			result = {
				...result,
				parsed: updatedParsed,
				validated,
				grid: nextGrid
			};
			syncGridToMap(nextGrid, false);
		} catch {
			/* ignore validation network errors */
		}
	}

	function removeFilter(index) {
		if (!result || !result.parsed) return;
		const nextFilters = result.parsed.filters.filter((_, idx) => idx !== index);
		const updatedParsed = {
			...result.parsed,
			intent: 'find_area',
			filters: nextFilters
		};
		revalidateParsed(updatedParsed);
	}

	function addManualFilter() {
		const baseParsed = result?.parsed || {
			intent: 'find_area',
			region: 'petrinja',
			filters: [],
			locations: [],
			layer: null,
			unsupported: []
		};
		const filtered = baseParsed.filters.filter((f) => f.hazard !== newHazard);
		const updatedParsed = {
			...baseParsed,
			intent: 'find_area',
			filters: [...filtered, { hazard: newHazard, max_level: newMaxLevel }]
		};
		if (!result) {
			result = {
				query: 'Ručni odabir filtera',
				parsed: updatedParsed,
				validated: null,
				grid: null,
				llm_used: false,
				model: 'ručni filteri'
			};
		}
		showGridOnMap = true;
		revalidateParsed(updatedParsed);
	}
</script>

<div class="nl-query-window no-print" aria-label="Pretraga prirodnim jezikom i filteri područja">
	<div class="nl-header">
		<div>
			<div class="nl-title-row">
				<h2><span aria-hidden="true">🔍</span> Pretraga područja prirodnim jezikom i filterima</h2>
				{#if result}
					<span class="llm-badge {result.llm_used ? 'llm-online' : 'llm-fallback'}">
						{result.llm_used ? `Ollama (${result.model})` : `Pravila / predložak (${result.model})`}
					</span>
				{/if}
			</div>
			<p class="nl-subtitle">
				Opišite kakvo područje tražite na hrvatskom jeziku. Sustav prevodi upit u provjerljive filtere nad katalogom otvorenih podataka i na karti označava odgovarajuće zone (H3 mreža).
			</p>
		</div>
	</div>

	<form
		class="nl-input-row"
		onsubmit={(e) => {
			e.preventDefault();
			submitQuery();
		}}
	>
		<label for="nl-query-input" class="sr-only">Unesite upit prirodnim jezikom na hrvatskom</label>
		<input
			id="nl-query-input"
			type="text"
			placeholder="Npr. Pronađi mi područja oko Petrinje bez poplava i s niskom podložnosti klizištima..."
			bind:value={queryText}
			maxlength="500"
		/>
		<button type="submit" class="btn-primary" disabled={loading || queryText.trim().length < 2}>
			{loading ? 'Pretraživanje...' : 'Pretraži područje'}
		</button>
	</form>

	<div class="nl-examples">
		<span class="examples-label">Primjeri upita:</span>
		{#each EXAMPLE_QUERIES as ex}
			<button type="button" class="example-chip" onclick={() => submitQuery(ex)}>
				{ex}
			</button>
		{/each}
	</div>

	{#if errorMsg}
		<div class="nl-error" role="alert">{errorMsg}</div>
	{/if}

	{#if result && result.validated}
		{@const val = result.validated}
		<div class="nl-result-box" aria-live="polite">
			<div class="nl-meta-bar">
				<div class="meta-item">
					<span class="meta-label">Namjera:</span>
					<strong>{INTENT_LABELS[val.intent] || val.intent}</strong>
				</div>
				{#if val.region}
					<div class="meta-item">
						<span class="meta-label">Regija:</span>
						<strong class="region-name">{val.region}</strong>
						<span class="coverage-pill {val.in_banovina ? 'cov-banovina' : 'cov-croatia'}">
							{val.in_banovina ? 'Obuhvat Banovina (svi slojevi)' : 'Izvan Banovine (nacionalni slojevi)'}
						</span>
					</div>
				{/if}
				{#if val.center}
					<button
						type="button"
						class="btn-small"
						onclick={() => {
							onSelectRegion(val.center, val.region);
							if (activeGrid) syncGridToMap(activeGrid, true);
						}}
					>
						📍 Prikaži regiju na karti
					</button>
				{/if}
			</div>

			{#if val.warnings && val.warnings.length > 0}
				<div class="nl-warnings" role="status">
					<strong>⚠️ Upozorenja kataloga slojeva (nepodržani kriteriji / obuhvat):</strong>
					<ul>
						{#each val.warnings as w}
							<li>{w}</li>
						{/each}
					</ul>
				</div>
			{/if}

			{#if activeGrid && activeGrid.summary}
				{@const s = activeGrid.summary}
				{@const activeRes = s.resolutions ? s.resolutions[activeH3Tier] ?? s.h3_resolution : s.h3_resolution}
				<div class="h3-grid-banner">
					<div class="h3-banner-top">
						<div>
							<strong>🗺️ Mrežna analiza područja ({s.region}):</strong>
							<span>
								Zadovoljava uvjete: <strong>{s.matched_cells}</strong> od <strong>{s.total_cells}</strong> baznih H3 ćelija
								(~<strong>{fmt(s.matched_area_km2, 1)} km²</strong>, bazna ćelija res {s.h3_resolution || 9} ~{fmt(s.cell_area_km2, 2)} km²).
							</span>
						</div>
						<div class="h3-toggles">
							<label class="h3-toggle">
								<input
									type="checkbox"
									bind:checked={showGridOnMap}
									onchange={() => syncGridToMap(activeGrid, false)}
								/>
								Prikaži H3 mrežu na karti
							</label>
							{#if showGridOnMap}
								<label class="h3-toggle">
									<input
										type="checkbox"
										bind:checked={showExcludedCells}
										onchange={() => syncGridToMap(activeGrid, false)}
									/>
									Prikaži i isključene ćelije
								</label>
							{/if}
						</div>
					</div>
					<div class="h3-legend-row">
						<span class="h3-swatch-item">
							<span class="h3-sw h3-sw-match" aria-hidden="true"></span>
							✓ Zadovoljava sve podržane filtere ({s.matched_cells})
						</span>
						{#if showExcludedCells}
							<span class="h3-swatch-item">
								<span class="h3-sw h3-sw-excl" aria-hidden="true"></span>
								✕ Isključeno barem jednim filterom ({s.excluded_cells})
							</span>
						{/if}
						{#if activeRes}
							<span class="h3-swatch-item">
								🔍 Trenutačni prikaz na karti: <strong>H3 res {activeRes}</strong> (zumirajte za promjenu veličine ćelija)
							</span>
						{/if}
					</div>
					{#if s.odbl_notice}
						<p class="h3-odbl">{s.odbl_notice}</p>
					{/if}
				</div>
			{/if}

			{#if val.intent === 'show_layer' && val.layer}
				<div class="nl-intent-card">
					<span>Zahtjev za prikaz sloja na karti: <strong>{LAYER_NAMES[val.layer] || val.layer}</strong></span>
					<button type="button" class="btn-small" onclick={() => onActivateLayer(val.layer)}>
						🗺️ Uključi sloj na karti
					</button>
				</div>
			{/if}

			{#if val.intent === 'compare_locations' && val.locations && val.locations.length > 0}
				<div class="nl-intent-card">
					<span>Prepoznate lokacije za usporedbu (kliknite za učitavanje izvještaja):</span>
					<div class="compare-chips">
						{#each val.locations as loc}
							<button type="button" class="chip" onclick={() => onSearchLocationText(loc)}>
								📍 {loc}
							</button>
						{/each}
					</div>
				</div>
			{/if}

			<div class="nl-filters-section">
				<div class="filters-title">
					<strong>Aktivni deterministički filteri ({val.supported_filters.length}):</strong>
					<span class="filters-hint">Filtere možete ukloniti ili ručno dodati (mreža na karti se odmah osvježava)</span>
				</div>

				{#if val.supported_filters.length > 0}
					<div class="filter-chips">
						{#each val.supported_filters as f, i}
							{@const hMeta = HAZARD_META[f.hazard] || { title: f.hazard, icon: '🔹' }}
							<span class="filter-chip">
								<span aria-hidden="true">{hMeta.icon}</span>
								<strong>{hMeta.title}:</strong>
								<span>{MAX_LEVEL_LABELS[f.max_level] || f.max_level}</span>
								<button
									type="button"
									class="chip-remove"
									aria-label="Ukloni filter {hMeta.title}"
									onclick={() => removeFilter(i)}
								>
									×
								</button>
							</span>
						{/each}
					</div>
				{:else}
					<p class="no-filters-msg">Nema aktivnih podržanih filtera za ovaj upit.</p>
				{/if}

				<div class="manual-filter-bar">
					<label>
						Opasnost:
						<select bind:value={newHazard}>
							<option value="flood">Poplave</option>
							<option value="seismic">Potresna opasnost</option>
							<option value="landslide">Podložnost klizištima</option>
							<option value="liquefaction">Podložnost likvefakciji</option>
							<option value="sinkhole">Podložnost vrtačama</option>
							<option value="unfavourable">Nepovoljno za gradnju</option>
							<option value="groundwater">Dubina podzemne vode</option>
						</select>
					</label>
					<label>
						Najviša dopuštena razina:
						<select bind:value={newMaxLevel}>
							<option value="nema_prema_karti">nema prema karti (bez opasnosti)</option>
							<option value="nisko">najviše nisko</option>
							<option value="srednje">najviše srednje</option>
							<option value="vrlo_niska_seizmicnost">vrlo niska seizmičnost (≤ 0,04 g)</option>
							<option value="niska_seizmicnost">niska seizmičnost (≤ 0,08 g)</option>
						</select>
					</label>
					<button type="button" class="btn-small" onclick={addManualFilter}>
						+ Dodaj / ažuriraj filter
					</button>
				</div>
			</div>

			<details class="json-details">
				<summary>Prikaži strukturirani JSON upit i sažetak izračuna</summary>
				<pre>{JSON.stringify(
						{
							parsed: result.parsed,
							validated: {
								intent: val.intent,
								region: val.region,
								in_banovina: val.in_banovina,
								supported_filters: val.supported_filters,
								warnings: val.warnings
							},
							h3_grid_summary: activeGrid?.summary || null
						},
						null,
						2
					)}</pre>
			</details>
		</div>
	{/if}
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
	.nl-query-window {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border);
	}
	.nl-title-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.nl-header h2 {
		margin: 0;
		font-size: 1.05rem;
		color: #0f172a;
	}
	.nl-subtitle {
		margin: 0.25rem 0 0.65rem 0;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.llm-badge {
		font-size: 0.75rem;
		font-weight: 700;
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		border: 1px solid;
	}
	.llm-online {
		background: #dcfce7;
		color: #166534;
		border-color: #86efac;
	}
	.llm-fallback {
		background: #f1f5f9;
		color: #334155;
		border-color: #cbd5e1;
	}
	.nl-input-row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.nl-input-row input {
		flex: 1;
		min-width: 240px;
		padding: 0.6rem 0.85rem;
		font-size: 0.95rem;
		border: 1.5px solid #64748b;
		border-radius: 0.5rem;
	}
	.nl-input-row input:focus {
		outline: 3px solid #93c5fd;
		border-color: var(--primary);
	}
	.btn-primary {
		padding: 0.6rem 1.1rem;
		font-weight: 700;
		background: #1d4ed8;
		color: #ffffff;
		border: 1px solid #1e40af;
		border-radius: 0.5rem;
		cursor: pointer;
	}
	.btn-primary:hover:not(:disabled) {
		background: #1e40af;
	}
	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.btn-small {
		padding: 0.35rem 0.7rem;
		font-size: 0.82rem;
		font-weight: 600;
		background: #eff6ff;
		color: #1e3a8a;
		border: 1px solid #93c5fd;
		border-radius: 0.375rem;
		cursor: pointer;
	}
	.btn-small:hover {
		background: #dbeafe;
	}
	.nl-examples {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		margin-top: 0.6rem;
	}
	.examples-label {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--muted);
	}
	.example-chip {
		background: #f8fafc;
		color: #334155;
		border: 1px solid #cbd5e1;
		border-radius: 0.375rem;
		padding: 0.25rem 0.55rem;
		font-size: 0.78rem;
		cursor: pointer;
		text-align: left;
	}
	.example-chip:hover {
		background: #eff6ff;
		border-color: #93c5fd;
		color: #1e3a8a;
	}
	.nl-error {
		margin-top: 0.6rem;
		padding: 0.6rem 0.85rem;
		background: var(--high-bg);
		border: 1px solid var(--high-border);
		color: var(--high-text);
		border-radius: 0.5rem;
		font-size: 0.88rem;
	}
	.nl-result-box {
		margin-top: 0.85rem;
		padding: 0.9rem 1rem;
		background: #f8fafc;
		border: 1px solid #cbd5e1;
		border-radius: 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.nl-meta-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.6rem;
		font-size: 0.88rem;
	}
	.meta-item {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
	}
	.meta-label {
		color: var(--muted);
	}
	.region-name {
		text-transform: capitalize;
	}
	.coverage-pill {
		font-size: 0.75rem;
		font-weight: 700;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
	}
	.cov-banovina {
		background: #dcfce7;
		color: #166534;
	}
	.cov-croatia {
		background: #dbeafe;
		color: #1e40af;
	}
	.nl-warnings {
		padding: 0.65rem 0.85rem;
		background: #fffbeb;
		border: 1px solid #f59e0b;
		color: #92400e;
		border-radius: 0.5rem;
		font-size: 0.86rem;
	}
	.nl-warnings ul {
		margin: 0.35rem 0 0 0;
		padding-left: 1.2rem;
	}
	.h3-grid-banner {
		padding: 0.7rem 0.85rem;
		background: #f0fdf4;
		border: 1.5px solid #86efac;
		border-radius: 0.5rem;
		font-size: 0.86rem;
		color: #14532d;
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}
	.h3-banner-top {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
	}
	.h3-toggles {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
	}
	.h3-toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-weight: 600;
		font-size: 0.8rem;
		cursor: pointer;
	}
	.h3-legend-row {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		font-size: 0.8rem;
		font-weight: 600;
	}
	.h3-swatch-item {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.h3-sw {
		width: 1rem;
		height: 0.75rem;
		border-radius: 0.15rem;
		display: inline-block;
	}
	.h3-sw-match {
		background: rgba(22, 163, 74, 0.55);
		border: 1.5px solid #15803d;
	}
	.h3-sw-excl {
		background: rgba(220, 38, 38, 0.28);
		border: 1.5px solid #b91c1c;
	}
	.h3-odbl {
		margin: 0;
		font-size: 0.76rem;
		color: #166534;
	}
	.nl-intent-card {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.6rem 0.8rem;
		background: #ffffff;
		border: 1px solid #e2e8f0;
		border-radius: 0.45rem;
		font-size: 0.88rem;
	}
	.compare-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
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
	.nl-filters-section {
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
	}
	.filters-title {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
		font-size: 0.86rem;
	}
	.filters-hint {
		font-size: 0.78rem;
		color: var(--muted);
	}
	.filter-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
	}
	.filter-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.3rem 0.6rem;
		background: #ffffff;
		border: 1.5px solid #2563eb;
		border-radius: 999px;
		font-size: 0.82rem;
		color: #1e293b;
	}
	.chip-remove {
		border: none;
		background: #e2e8f0;
		color: #0f172a;
		border-radius: 999px;
		width: 1.25rem;
		height: 1.25rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-weight: 800;
		cursor: pointer;
		margin-left: 0.15rem;
	}
	.chip-remove:hover {
		background: #cbd5e1;
	}
	.no-filters-msg {
		margin: 0;
		font-size: 0.84rem;
		color: var(--muted);
	}
	.manual-filter-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		padding-top: 0.4rem;
		border-top: 1px dashed #cbd5e1;
		font-size: 0.82rem;
	}
	.manual-filter-bar label {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-weight: 600;
	}
	.manual-filter-bar select {
		padding: 0.25rem 0.45rem;
		border: 1px solid #94a3b8;
		border-radius: 0.35rem;
		font-size: 0.82rem;
		background: #ffffff;
	}
	.json-details {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.json-details summary {
		cursor: pointer;
		font-weight: 600;
	}
	.json-details pre {
		margin: 0.4rem 0 0 0;
		padding: 0.65rem;
		background: #0f172a;
		color: #e2e8f0;
		border-radius: 0.4rem;
		overflow-x: auto;
		font-size: 0.78rem;
	}
</style>
