import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		// SPA mode: unknown paths (e.g. a reload of /izvori) fall back to index.html.
		adapter: adapter({ fallback: 'index.html' })
	}
};

export default config;
