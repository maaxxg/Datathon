<script>
	// Print-only header of the report (hidden on screen via print.css).
	// APP_NAME is the working name; change it here only.
	const APP_NAME = 'Geo-rizik';

	let { generatedAt = null } = $props();

	const pad = (n) => String(n).padStart(2, '0');
	// d. m. yyyy. u HH:mm, local time, no locale-dependent API.
	const stamp = $derived(
		generatedAt
			? `${generatedAt.getDate()}. ${generatedAt.getMonth() + 1}. ${generatedAt.getFullYear()}. u ${pad(generatedAt.getHours())}:${pad(generatedAt.getMinutes())}`
			: null
	);
	const sourcesUrl = typeof window === 'undefined' ? '/izvori' : `${window.location.origin}/izvori`;
</script>

<div class="print-only">
	<p class="print-title">{APP_NAME} — izvještaj o izloženosti prirodnim opasnostima</p>
	{#if stamp}<p>Izvještaj izrađen: {stamp}</p>{/if}
	<p>Popis svih izvora podataka i licenci: {sourcesUrl}</p>
	<p>Karta nije dio ispisa; lokacija je navedena koordinatama WGS84.</p>
</div>
