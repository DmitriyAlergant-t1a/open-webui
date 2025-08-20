<script lang="ts">
	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import FileBrowser from './FileBrowser.svelte';
	import { getContext } from 'svelte';

	export let chatId: string;
	export let expanded = false;

	function toggleExpanded() {
		expanded = !expanded;
		// Save state to localStorage
		localStorage.setItem('fileBrowserExpanded', expanded.toString());
	}

	// Load initial state from localStorage
	if (typeof window !== 'undefined') {
		const saved = localStorage.getItem('fileBrowserExpanded');
		if (saved !== null) {
			expanded = saved === 'true';
		}
	}
</script>


<div class="bg-transparent flex justify-center">
	<div class="file-browser-panel max-w-6xl rounded-3xl">
		<!-- Collapsible content -->
		{#if expanded}
			<div class="p-3">
				<FileBrowser {chatId} height="350px" />
			</div>
		{/if}
	</div>
</div>

<style>
	.file-browser-panel {
		background: white;
	}
	
	:global(.dark) .file-browser-panel {
		background: #1f2937;
	}
</style>