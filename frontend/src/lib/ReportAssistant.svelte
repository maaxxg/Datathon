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

<section class="assistant-section no-print" aria-label="Dodatno objašnjenje i pitanja o izvještaju">
	<div class="assistant-header">
		<div>
			<h3><span aria-hidden="true">🤖</span> Dodatno objašnjenje i pitanja o izvještaju</h3>
			<p class="assistant-sub">
				AI ne računa razine opasnosti — sažima i odgovara isključivo na temelju gornjeg determinističkog izvještaja.
			</p>
		</div>
		<button
			type="button"
			class="btn-explain"
			onclick={generateExplanation}
			disabled={loadingExplain}
		>
			{loadingExplain ? 'Generiranje...' : aiExplanation ? '🔄 Obnovi objašnjenje' : '✨ Generiraj sažeto objašnjenje'}
		</button>
	</div>

	{#if explainError}
		<div class="assistant-error" role="alert">{explainError}</div>
	{/if}

	{#if aiExplanation}
		<div class="explanation-box" aria-live="polite">
			<div class="explanation-meta">
				<strong>Sažeto objašnjenje izvještaja</strong>
				<span class="mode-tag {explainLlmUsed ? 'tag-llm' : 'tag-tpl'}">
					{explainLlmUsed ? `Ollama (${explainModel})` : explainModel}
				</span>
			</div>
			<div class="explanation-text">
				{#each aiExplanation.split('\n\n') as para}
					<p>{para}</p>
				{/each}
			</div>
		</div>
	{/if}

	<div class="qa-box">
		<h4>Pitaj o ovom izvještaju</h4>
		<div class="suggested-row">
			{#each SUGGESTED_QUESTIONS as sq}
				<button
					type="button"
					class="sq-chip"
					disabled={loadingAsk}
					onclick={() => submitQuestion(sq)}
				>
					{sq}
				</button>
			{/each}
		</div>

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
				type="text"
				placeholder="Postavite pitanje o ovom izvještaju (npr. Što znači podložnost likvefakciji?)..."
				bind:value={questionInput}
				maxlength="400"
			/>
			<button
				type="submit"
				class="btn-ask"
				disabled={loadingAsk || questionInput.trim().length < 2}
			>
				{loadingAsk ? 'Slanje...' : 'Pitaj'}
			</button>
		</form>

		{#if askError}
			<div class="assistant-error" role="alert">{askError}</div>
		{/if}

		{#if qaHistory.length > 0}
			<div class="qa-list" aria-live="polite">
				{#each qaHistory as item}
					<div class="qa-item">
						<div class="qa-q">
							<strong>Pitanje:</strong> {item.question}
						</div>
						<div class="qa-a">
							<div class="qa-a-header">
								<strong>Odgovor:</strong>
								<span class="mode-tag {item.llm_used ? 'tag-llm' : 'tag-tpl'}">
									{item.llm_used ? `Ollama (${item.model})` : item.model}
								</span>
							</div>
							{#each item.answer.split('\n\n') as para}
								<p>{para}</p>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</section>

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
	.assistant-section {
		margin-top: 1.25rem;
		background: var(--surface);
		border: 1.5px solid #93c5fd;
		border-radius: 0.75rem;
		padding: 1rem 1.25rem;
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}
	.assistant-header {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
	}
	.assistant-header h3 {
		margin: 0;
		font-size: 1.05rem;
		color: #0f172a;
	}
	.assistant-sub {
		margin: 0.2rem 0 0 0;
		font-size: 0.83rem;
		color: var(--muted);
	}
	.btn-explain {
		padding: 0.5rem 0.9rem;
		font-size: 0.86rem;
		font-weight: 700;
		background: #eff6ff;
		color: #1e3a8a;
		border: 1.5px solid #3b82f6;
		border-radius: 0.5rem;
		cursor: pointer;
		white-space: nowrap;
	}
	.btn-explain:hover:not(:disabled) {
		background: #dbeafe;
	}
	.btn-explain:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.explanation-box {
		background: #f8fafc;
		border: 1px solid #cbd5e1;
		border-radius: 0.5rem;
		padding: 0.8rem 0.95rem;
	}
	.explanation-meta {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.45rem;
		font-size: 0.84rem;
	}
	.explanation-text p {
		margin: 0 0 0.5rem 0;
		font-size: 0.9rem;
		white-space: pre-line;
	}
	.explanation-text p:last-child {
		margin-bottom: 0;
	}
	.mode-tag {
		font-size: 0.73rem;
		font-weight: 700;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		border: 1px solid;
	}
	.tag-llm {
		background: #dcfce7;
		color: #166534;
		border-color: #86efac;
	}
	.tag-tpl {
		background: #f1f5f9;
		color: #334155;
		border-color: #cbd5e1;
	}
	.qa-box {
		border-top: 1px solid #e2e8f0;
		padding-top: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.qa-box h4 {
		margin: 0;
		font-size: 0.95rem;
	}
	.suggested-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.sq-chip {
		background: #f8fafc;
		color: #334155;
		border: 1px solid #cbd5e1;
		border-radius: 0.375rem;
		padding: 0.25rem 0.55rem;
		font-size: 0.78rem;
		cursor: pointer;
		text-align: left;
	}
	.sq-chip:hover:not(:disabled) {
		background: #eff6ff;
		border-color: #93c5fd;
		color: #1e3a8a;
	}
	.qa-form {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.qa-form input {
		flex: 1;
		min-width: 200px;
		padding: 0.55rem 0.8rem;
		font-size: 0.92rem;
		border: 1.5px solid #64748b;
		border-radius: 0.45rem;
	}
	.qa-form input:focus {
		outline: 3px solid #93c5fd;
		border-color: var(--primary);
	}
	.btn-ask {
		padding: 0.55rem 1rem;
		font-weight: 700;
		background: #1d4ed8;
		color: #ffffff;
		border: 1px solid #1e40af;
		border-radius: 0.45rem;
		cursor: pointer;
	}
	.btn-ask:hover:not(:disabled) {
		background: #1e40af;
	}
	.btn-ask:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.assistant-error {
		padding: 0.55rem 0.75rem;
		background: var(--high-bg);
		border: 1px solid var(--high-border);
		color: var(--high-text);
		border-radius: 0.45rem;
		font-size: 0.85rem;
	}
	.qa-list {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		margin-top: 0.25rem;
	}
	.qa-item {
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 0.5rem;
		padding: 0.7rem 0.85rem;
		font-size: 0.88rem;
	}
	.qa-q {
		margin-bottom: 0.4rem;
		color: #0f172a;
	}
	.qa-a-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 0.25rem;
	}
	.qa-a p {
		margin: 0 0 0.4rem 0;
		color: #334155;
		white-space: pre-line;
	}
	.qa-a p:last-child {
		margin-bottom: 0;
	}
</style>
