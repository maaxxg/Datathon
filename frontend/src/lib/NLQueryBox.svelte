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

<section class="nl-query no-print" aria-labelledby="nl-heading">
	<div class="nl-head">
		<div class="nl-head-text">
			<h2 id="nl-heading">Pretraga područja prirodnim jezikom</h2>
			<p class="nl-subtitle">
				Opišite kakvo područje tražite na hrvatskom jeziku. Sustav prevodi upit u provjerljive filtere nad katalogom otvorenih podataka i na karti označava odgovarajuće zone (H3 mreža).
			</p>
		</div>
		{#if result}
			<span class="engine-tag {result.llm_used ? 'engine-llm' : 'engine-rules'}">
				{result.llm_used ? `Ollama · ${result.model}` : `Pravila · ${result.model}`}
			</span>
		{/if}
	</div>

	<form
		class="nl-input-row"
		onsubmit={(e) => {
			e.preventDefault();
			submitQuery();
		}}
	>
		<label for="nl-query-input" class="sr-only">Unesite upit prirodnim jezikom na hrvatskom</label>
		<div class="prompt">
			<span class="prompt-sign" aria-hidden="true">›</span>
			<input
				id="nl-query-input"
				type="text"
				placeholder="npr. područja oko Petrinje bez poplava i s niskom podložnosti klizištima"
				bind:value={queryText}
				maxlength="500"
			/>
		</div>
		<button type="submit" class="btn" disabled={loading || queryText.trim().length < 2}>
			{loading ? 'Pretraživanje…' : 'Pretraži područje'}
		</button>
	</form>

	<div class="nl-examples">
		<span class="examples-label">Primjeri upita:</span>
		<ul class="example-chips">
			{#each EXAMPLE_QUERIES as ex}
				<li>
					<button type="button" class="example" onclick={() => submitQuery(ex)}>„{ex}“</button>
				</li>
			{/each}
		</ul>
	</div>

	{#if errorMsg}
		<div class="nl-error" role="alert">{errorMsg}</div>
	{/if}

	{#if result && result.validated}
		{@const val = result.validated}
		<div class="nl-result" aria-live="polite">
			<dl class="nl-meta">
				<div>
					<dt>Namjera</dt>
					<dd>{INTENT_LABELS[val.intent] || val.intent}</dd>
				</div>
				{#if val.region}
					<div>
						<dt>Regija</dt>
						<dd>
							<span class="region-name">{val.region}</span>
							<span class="coverage {val.in_banovina ? 'cov-banovina' : 'cov-croatia'}">
								{val.in_banovina ? 'Obuhvat Banovina (svi slojevi)' : 'Izvan Banovine (nacionalni slojevi)'}
							</span>
						</dd>
					</div>
				{/if}
				{#if val.center}
					<div class="meta-action">
						<button
							type="button"
							class="btn btn-ghost btn-sm"
							onclick={() => {
								onSelectRegion(val.center, val.region);
								if (activeGrid) syncGridToMap(activeGrid, true);
							}}
						>
							Prikaži regiju na karti
						</button>
					</div>
				{/if}
			</dl>

			{#if val.warnings && val.warnings.length > 0}
				<div class="nl-warnings" role="status">
					<strong>Upozorenja kataloga slojeva (nepodržani kriteriji / obuhvat)</strong>
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
				<div class="h3-panel">
					<div class="h3-top">
						<div class="h3-figure">
							<span class="h3-big">{s.matched_cells}<span class="h3-of">/{s.total_cells}</span></span>
							<span class="h3-cap">baznih H3 ćelija zadovoljava uvjete · {s.region}</span>
						</div>
						<div class="h3-figure">
							<span class="h3-big">{fmt(s.matched_area_km2, 1)}<span class="h3-of"> km²</span></span>
							<span class="h3-cap">bazna ćelija res {s.h3_resolution || 9} ≈ {fmt(s.cell_area_km2, 2)} km²</span>
						</div>
					</div>
					<div class="h3-controls">
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
					<ul class="h3-legend">
						<li>
							<span class="h3-sw h3-sw-match" aria-hidden="true"></span>
							Zadovoljava sve podržane filtere ({s.matched_cells})
						</li>
						{#if showExcludedCells}
							<li>
								<span class="h3-sw h3-sw-excl" aria-hidden="true"></span>
								Isključeno barem jednim filterom ({s.excluded_cells})
							</li>
						{/if}
						{#if activeRes}
							<li class="h3-res">
								Prikaz na karti: <strong>H3 res {activeRes}</strong> (zumirajte za promjenu veličine ćelija)
							</li>
						{/if}
					</ul>
					{#if s.odbl_notice}
						<p class="h3-odbl">{s.odbl_notice}</p>
					{/if}
				</div>
			{/if}

			{#if val.intent === 'show_layer' && val.layer}
				<div class="nl-intent">
					<span>Zahtjev za prikaz sloja na karti: <strong>{LAYER_NAMES[val.layer] || val.layer}</strong></span>
					<button type="button" class="btn btn-ghost btn-sm" onclick={() => onActivateLayer(val.layer)}>
						Uključi sloj na karti
					</button>
				</div>
			{/if}

			{#if val.intent === 'compare_locations' && val.locations && val.locations.length > 0}
				<div class="nl-intent">
					<span>Prepoznate lokacije za usporedbu (kliknite za učitavanje izvještaja):</span>
					<div class="compare-list">
						{#each val.locations as loc}
							<button type="button" class="btn btn-ghost btn-sm" onclick={() => onSearchLocationText(loc)}>
								{loc}
							</button>
						{/each}
					</div>
				</div>
			{/if}

			<div class="nl-filters">
				<div class="filters-title">
					<strong>Aktivni deterministički filteri <span class="count">({val.supported_filters.length})</span></strong>
					<span class="filters-hint">Filtere možete ukloniti ili ručno dodati (mreža na karti se odmah osvježava)</span>
				</div>

				{#if val.supported_filters.length > 0}
					<ul class="filter-list">
						{#each val.supported_filters as f, i}
							{@const hMeta = HAZARD_META[f.hazard] || { title: f.hazard, code: '··' }}
							<li class="filter">
								<span class="hz-code">{hMeta.code}</span>
								<span><strong>{hMeta.title}:</strong> {MAX_LEVEL_LABELS[f.max_level] || f.max_level}</span>
								<button
									type="button"
									class="filter-remove"
									aria-label="Ukloni filter {hMeta.title}"
									onclick={() => removeFilter(i)}
								>
									×
								</button>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="no-filters-msg">Nema aktivnih podržanih filtera za ovaj upit.</p>
				{/if}

				<div class="manual-filter-bar">
					<label>
						<span>Opasnost</span>
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
						<span>Najviša dopuštena razina</span>
						<select bind:value={newMaxLevel}>
							<option value="nema_prema_karti">nema prema karti (bez opasnosti)</option>
							<option value="nisko">najviše nisko</option>
							<option value="srednje">najviše srednje</option>
							<option value="vrlo_niska_seizmicnost">vrlo niska seizmičnost (≤ 0,04 g)</option>
							<option value="niska_seizmicnost">niska seizmičnost (≤ 0,08 g)</option>
						</select>
					</label>
					<button type="button" class="btn btn-sm" onclick={addManualFilter}>
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
</section>

<style>
	.nl-query {
		padding: 1.1rem 1.25rem 1.25rem;
		background: var(--surface);
		border: 1.5px solid var(--ink);
		box-shadow: 5px 5px 0 var(--paper-2);
	}
	.nl-head {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.5rem 1rem;
	}
	.nl-head-text {
		flex: 1;
		min-width: 260px;
	}
	.nl-head h2 {
		margin: 0;
		font-size: 1.2rem;
	}
	.nl-subtitle {
		margin: 0.25rem 0 0.8rem 0;
		max-width: 80ch;
		font-size: 0.88rem;
		color: var(--muted);
	}
	.engine-tag {
		font-family: var(--mono);
		font-size: 0.72rem;
		padding: 0.15rem 0.5rem;
		border: 1px solid currentColor;
		white-space: nowrap;
	}
	.engine-llm {
		color: var(--low-text);
		background: var(--low-bg);
	}
	.engine-rules {
		color: var(--ink-2);
		background: var(--paper);
	}
	.nl-input-row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.prompt {
		flex: 1;
		min-width: 240px;
		display: flex;
		align-items: center;
		background: var(--paper);
		border: 1.5px solid var(--ink);
		border-radius: 2px;
	}
	.prompt:focus-within {
		outline: 3px solid #f0c9a8;
		border-color: var(--accent-ink);
	}
	.prompt-sign {
		padding: 0 0.2rem 0 0.75rem;
		font-family: var(--mono);
		font-size: 1.15rem;
		font-weight: 700;
		color: var(--accent);
	}
	.prompt input {
		flex: 1;
		min-width: 0;
		min-height: 2.5rem;
		padding: 0.5rem 0.75rem 0.5rem 0.4rem;
		border: none;
		background: transparent;
		font-family: var(--mono);
		font-size: 0.9rem;
		color: var(--ink);
	}
	.prompt input::placeholder {
		color: #77725f;
	}
	.prompt input:focus {
		outline: none;
	}
	.nl-examples {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		margin-top: 0.85rem;
	}
	.examples-label {
		font-size: 0.74rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.example-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.example {
		display: inline-flex;
		align-items: baseline;
		gap: 0.35rem;
		min-height: 1.95rem;
		padding: 0.3rem 0.65rem;
		font-family: var(--serif);
		font-style: italic;
		font-size: 0.85rem;
		color: var(--ink-2);
		background: var(--surface);
		border: 1px dashed #8c826e;
		border-radius: 2px;
		text-align: left;
		cursor: pointer;
		transition: all 0.12s ease;
		line-height: 1.35;
	}
	.example::before {
		content: '↳';
		font-family: var(--mono);
		font-style: normal;
		font-size: 0.82rem;
		color: var(--accent);
		flex: none;
	}
	.example:hover {
		background: var(--paper-2);
		border-style: solid;
		border-color: var(--accent-ink);
		color: var(--ink);
		box-shadow: 2px 2px 0 rgba(29, 28, 26, 0.08);
	}
	.nl-error {
		margin-top: 0.75rem;
		padding: 0.6rem 0.85rem;
		background: var(--high-bg);
		border: 1.5px solid var(--high-border);
		color: var(--high-text);
		font-size: 0.88rem;
	}
	.nl-result {
		margin-top: 1rem;
		padding-top: 0.9rem;
		border-top: 1px solid var(--rule);
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}
	.nl-meta {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 0.6rem 2rem;
		margin: 0;
		font-size: 0.9rem;
	}
	.nl-meta dt {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.nl-meta dd {
		margin: 0.1rem 0 0 0;
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.5rem;
		font-weight: 600;
	}
	.meta-action {
		margin-left: auto;
	}
	.region-name {
		text-transform: capitalize;
	}
	.coverage {
		font-family: var(--mono);
		font-size: 0.72rem;
		font-weight: 400;
		padding: 0.05rem 0.4rem;
		border: 1px solid currentColor;
	}
	.cov-banovina {
		color: var(--low-text);
		background: var(--low-bg);
	}
	.cov-croatia {
		color: var(--none-text);
		background: var(--none-bg);
	}
	.nl-warnings {
		padding: 0.6rem 0.85rem;
		background: var(--med-bg);
		border-left: 4px solid var(--med-border);
		color: var(--med-text);
		font-size: 0.86rem;
	}
	.nl-warnings ul {
		margin: 0.3rem 0 0 0;
		padding-left: 1.2rem;
	}
	.h3-panel {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding: 0.85rem 1rem;
		background: var(--paper);
		border: 1px solid var(--hair);
		font-size: 0.86rem;
	}
	.h3-top {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 2.5rem;
	}
	.h3-figure {
		display: flex;
		flex-direction: column;
	}
	.h3-big {
		font-family: var(--serif);
		font-size: 1.9rem;
		font-weight: 700;
		line-height: 1;
		color: var(--low-text);
	}
	.h3-of {
		font-size: 1rem;
		color: var(--muted);
		font-weight: 400;
	}
	.h3-cap {
		margin-top: 0.2rem;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.h3-controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.25rem;
	}
	.h3-toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 1.75rem;
		font-weight: 600;
		cursor: pointer;
	}
	.h3-toggle input {
		width: 1.15rem;
		height: 1.15rem;
		margin: 0;
		accent-color: var(--ink);
	}
	.h3-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.25rem;
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: 0.8rem;
	}
	.h3-legend li {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
	}
	.h3-sw {
		width: 1.1rem;
		height: 0.8rem;
		display: inline-block;
	}
	.h3-sw-match {
		background: rgba(77, 107, 34, 0.5);
		border: 1.5px solid #3a5219;
	}
	.h3-sw-excl {
		background: rgba(158, 42, 20, 0.22);
		border: 1.5px solid #7d200f;
	}
	.h3-res {
		color: var(--muted);
	}
	.h3-odbl {
		margin: 0;
		font-size: 0.76rem;
		color: var(--muted);
	}
	.nl-intent {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.6rem 0;
		border-top: 1px solid var(--hair);
		border-bottom: 1px solid var(--hair);
		font-size: 0.9rem;
	}
	.compare-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.nl-filters {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.filters-title {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.25rem 1rem;
		font-size: 0.9rem;
	}
	.count {
		font-family: var(--mono);
		font-weight: 400;
		color: var(--muted);
	}
	.filters-hint {
		font-size: 0.78rem;
		color: var(--muted);
	}
	.filter-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.filter {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.2rem 0.25rem 0.2rem 0.2rem;
		background: var(--paper);
		border: 1px solid var(--ink);
		font-size: 0.84rem;
	}
	.filter .hz-code {
		height: 1.35rem;
		min-width: 1.9rem;
		font-size: 0.7rem;
		border-width: 1px;
	}
	.filter-remove {
		width: 1.6rem;
		height: 1.6rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: none;
		border-left: 1px solid var(--hair);
		background: transparent;
		color: var(--ink);
		font-size: 1.05rem;
		cursor: pointer;
	}
	.filter-remove:hover {
		background: var(--high-bg);
		color: var(--high-text);
	}
	.no-filters-msg {
		margin: 0;
		font-size: 0.86rem;
		color: var(--muted);
	}
	.manual-filter-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 0.6rem 1rem;
		padding-top: 0.6rem;
		border-top: 1px dashed var(--hair);
		font-size: 0.84rem;
	}
	.manual-filter-bar label {
		display: inline-flex;
		flex-direction: column;
		gap: 0.2rem;
	}
	.manual-filter-bar label span {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.manual-filter-bar select {
		min-height: 2rem;
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--ink);
		border-radius: 2px;
		font-family: var(--sans);
		font-size: 0.85rem;
		background: var(--surface);
		color: var(--ink);
	}
	.json-details {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.json-details summary {
		cursor: pointer;
		font-family: var(--mono);
	}
	.json-details pre {
		margin: 0.4rem 0 0 0;
		padding: 0.75rem;
		background: var(--ink);
		color: #e9e2d0;
		overflow-x: auto;
		font-size: 0.76rem;
	}
</style>
