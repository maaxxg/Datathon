<script>
	let { report } = $props();

	const SUGGESTED_QUESTIONS = [
		'Što znači najznačajniji rizik na ovoj lokaciji?',
		'Zašto za neke opasnosti piše da nema podataka?',
		'Koji su preporučeni koraci i kome se obratiti?',
		'Koji su izvori i ograničenja podataka o potresu i poplavi?'
	];

	let aiExplanation = $state('');
	let explainModel = $state('');
	let explainLlmUsed = $state(false);
	let loadingExplain = $state(false);
	let explainError = $state('');

	let questionInput = $state('');
	let loadingAsk = $state(false);
	let askError = $state('');
	let qaHistory = $state([]);

	// Reset explanation and Q&A history whenever the active report changes
	$effect(() => {
		if (report) {
			aiExplanation = '';
			explainModel = '';
			explainLlmUsed = false;
			explainError = '';
			qaHistory = [];
			askError = '';
		}
	});

	async function generateExplanation() {
		if (!report || loadingExplain) return;
		loadingExplain = true;
		explainError = '';
		try {
			const res = await fetch('/api/report/explain', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ report })
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				throw new Error(err.detail || `Greška pri generiranju objašnjenja (${res.status})`);
			}
			const data = await res.json();
			aiExplanation = data.explanation || '';
			explainLlmUsed = !!data.llm_used;
			explainModel = data.model || '';
		} catch (e) {
			explainError = e.message || 'Nije moguće generirati objašnjenje.';
		} finally {
			loadingExplain = false;
		}
	}

	async function submitQuestion(qText = questionInput) {
		const trimmed = (qText || '').trim();
		if (!report || trimmed.length < 2 || loadingAsk) return;
		questionInput = '';
		loadingAsk = true;
		askError = '';
		try {
			const res = await fetch('/api/report/ask', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ question: trimmed, report })
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				throw new Error(err.detail || `Greška pri slanju pitanja (${res.status})`);
			}
			const data = await res.json();
			qaHistory = [
				...qaHistory,
				{
					question: trimmed,
					answer: data.answer || '',
					llm_used: !!data.llm_used,
					model: data.model || ''
				}
			];
		} catch (e) {
			askError = e.message || 'Nije moguće dobiti odgovor.';
		} finally {
			loadingAsk = false;
		}
	}
</script>

<section class="assistant no-print" aria-label="Dodatno objašnjenje i pitanja o izvještaju">
	<div class="section-head">
		<h3>Objašnjenje i pitanja o izvještaju</h3>
		<button type="button" class="btn btn-ghost btn-sm" onclick={generateExplanation} disabled={loadingExplain}>
			{loadingExplain ? 'Generiranje…' : aiExplanation ? 'Obnovi objašnjenje' : 'Generiraj sažeto objašnjenje'}
		</button>
	</div>
	<p class="assistant-note">
		AI ne računa razine opasnosti — sažima i odgovara isključivo na temelju gornjeg determinističkog izvještaja.
	</p>

	{#if explainError}
		<div class="assistant-error" role="alert">{explainError}</div>
	{/if}

	{#if aiExplanation}
		<div class="explanation" aria-live="polite">
			<div class="explanation-meta">
				<span class="kicker">Sažeto objašnjenje izvještaja</span>
				<span class="mode-tag {explainLlmUsed ? 'tag-llm' : 'tag-tpl'}">
					{explainLlmUsed ? `Ollama · ${explainModel}` : explainModel}
				</span>
			</div>
			<div class="explanation-text">
				{#each aiExplanation.split('\n\n') as para}
					<p>{para}</p>
				{/each}
			</div>
		</div>
	{/if}

	<div class="qa">
		<h4 class="kicker">Pitaj o ovom izvještaju</h4>
		<ul class="suggested">
			{#each SUGGESTED_QUESTIONS as sq}
				<li>
					<button type="button" class="sq" disabled={loadingAsk} onclick={() => submitQuestion(sq)}>
						{sq}
					</button>
				</li>
			{/each}
		</ul>

		<form
			class="qa-form"
			onsubmit={(e) => {
				e.preventDefault();
				submitQuestion();
			}}
		>
			<label for="report-qa-input" class="sr-only">Postavite pitanje o ovom izvještaju</label>
			<input
				id="report-qa-input"
				class="field"
				type="text"
				placeholder="npr. Što znači podložnost likvefakciji?"
				bind:value={questionInput}
				maxlength="400"
			/>
			<button type="submit" class="btn" disabled={loadingAsk || questionInput.trim().length < 2}>
				{loadingAsk ? 'Slanje…' : 'Pitaj'}
			</button>
		</form>

		{#if askError}
			<div class="assistant-error" role="alert">{askError}</div>
		{/if}

		{#if qaHistory.length > 0}
			<ol class="qa-list" aria-live="polite">
				{#each qaHistory as item}
					<li class="qa-item">
						<div class="qa-q">
							<span class="qa-mark" aria-hidden="true">P</span>
							<p><span class="sr-only">Pitanje:</span> {item.question}</p>
						</div>
						<div class="qa-a">
							<span class="qa-mark qa-mark-a" aria-hidden="true">O</span>
							<div>
								<span class="sr-only">Odgovor:</span>
								{#each item.answer.split('\n\n') as para}
									<p>{para}</p>
								{/each}
								<span class="mode-tag {item.llm_used ? 'tag-llm' : 'tag-tpl'}">
									{item.llm_used ? `Ollama · ${item.model}` : item.model}
								</span>
							</div>
						</div>
					</li>
				{/each}
			</ol>
		{/if}
	</div>
</section>

<style>
	.assistant {
		margin-top: 2rem;
	}
	.section-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--rule);
		padding-bottom: 0.4rem;
	}
	.section-head h3 {
		margin: 0;
		font-size: 1.12rem;
	}
	.assistant-note {
		margin: 0.4rem 0 0.9rem 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.kicker {
		margin: 0;
		font-family: var(--sans);
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.explanation {
		margin-bottom: 1rem;
		padding: 0.85rem 1rem;
		background: var(--surface);
		border-left: 3px solid var(--ink);
	}
	.explanation-meta {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.45rem;
	}
	.explanation-text p {
		margin: 0 0 0.6rem 0;
		font-family: var(--serif);
		font-size: 0.98rem;
		line-height: 1.55;
		white-space: pre-line;
		max-width: 66ch;
	}
	.explanation-text p:last-child {
		margin-bottom: 0;
	}
	.mode-tag {
		display: inline-block;
		font-family: var(--mono);
		font-size: 0.7rem;
		padding: 0.05rem 0.4rem;
		border: 1px solid currentColor;
	}
	.tag-llm {
		color: var(--low-text);
		background: var(--low-bg);
	}
	.tag-tpl {
		color: var(--ink-2);
		background: var(--paper);
	}
	.qa {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.suggested {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin: 0.35rem 0 0.2rem 0;
		padding: 0;
		list-style: none;
	}
	.sq {
		display: inline-flex;
		align-items: baseline;
		gap: 0.35rem;
		min-height: 1.85rem;
		padding: 0.25rem 0.65rem;
		background: var(--surface);
		border: 1px dashed #8c826e;
		border-radius: 2px;
		font-family: var(--sans);
		font-size: 0.82rem;
		color: var(--ink-2);
		text-align: left;
		cursor: pointer;
		transition: all 0.12s ease;
	}
	.sq::before {
		content: '?';
		font-family: var(--mono);
		font-weight: 700;
		font-size: 0.78rem;
		color: var(--accent);
		flex: none;
	}
	.sq:hover:not(:disabled) {
		color: var(--ink);
		background: var(--paper-2);
		border-style: solid;
		border-color: var(--accent-ink);
		box-shadow: 2px 2px 0 rgba(29, 28, 26, 0.08);
	}
	.sq:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.qa-form {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-top: 0.2rem;
	}
	.qa-form input {
		flex: 1;
		min-width: 200px;
		width: auto;
	}
	.qa-form .btn {
		min-height: 2.75rem;
	}
	.assistant-error {
		padding: 0.55rem 0.75rem;
		background: var(--high-bg);
		border: 1.5px solid var(--high-border);
		color: var(--high-text);
		font-size: 0.85rem;
	}
	.qa-list {
		display: flex;
		flex-direction: column;
		gap: 0;
		margin: 0.3rem 0 0 0;
		padding: 0;
		list-style: none;
	}
	.qa-item {
		padding: 0.8rem 0;
		border-bottom: 1px solid var(--hair);
		font-size: 0.9rem;
	}
	.qa-q,
	.qa-a {
		display: grid;
		grid-template-columns: 1.6rem minmax(0, 1fr);
		gap: 0.5rem;
	}
	.qa-q p {
		margin: 0;
		font-weight: 600;
	}
	.qa-a {
		margin-top: 0.45rem;
	}
	.qa-mark {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.4rem;
		height: 1.4rem;
		font-family: var(--mono);
		font-size: 0.75rem;
		font-weight: 700;
		border: 1px solid var(--ink);
	}
	.qa-mark-a {
		background: var(--ink);
		color: var(--paper);
	}
	.qa-a p {
		margin: 0 0 0.45rem 0;
		font-family: var(--serif);
		color: var(--ink-2);
		white-space: pre-line;
	}
</style>
