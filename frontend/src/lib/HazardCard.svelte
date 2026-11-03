<script>
	import { HAZARD_META, LEVEL_META, FLOOD_DEPTH_TEXT, fmt } from '$lib/labels.js';

	let { h } = $props();

	let meta = $derived(HAZARD_META[h.hazard] || { title: h.hazard, subtitle: '', icon: 'ℹ️' });
	let lvl = $derived(LEVEL_META[h.level] || LEVEL_META.nema_podataka);
</script>

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
			{#if h.source.url && h.source.url !== 'TBD'}
				<a href={h.source.url} target="_blank" rel="noopener noreferrer">Poveznica na izvor ↗</a>
			{/if}
			{#if h.source.note}
				<span class="source-note">{h.source.note}</span>
			{/if}
		</footer>
	{/if}
</article>

<style>
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
</style>

