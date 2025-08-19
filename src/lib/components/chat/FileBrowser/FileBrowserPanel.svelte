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

<div class="file-browser-panel border-t border-gray-200 dark:border-gray-700">
	<!-- Header with toggle button -->
	<div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800">
		<div class="flex items-center gap-2">
			<svg
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				xmlns="http://www.w3.org/2000/svg"
				class="text-gray-600 dark:text-gray-400"
			>
				<path
					d="M10 4H4C3.44772 4 3 4.44772 3 5V19C3 19.5523 3.44772 20 4 20H20C20.5523 20 21 19.5523 21 19V8C21 7.44772 20.5523 7 20 7H12L10 4Z"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
			<span class="text-sm font-medium text-gray-700 dark:text-gray-300">File Browser</span>
		</div>
		
		<button
			on:click={toggleExpanded}
			class="flex items-center justify-center w-6 h-6 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
		>
			<svg
				width="12"
				height="12"
				viewBox="0 0 24 24"
				fill="none"
				xmlns="http://www.w3.org/2000/svg"
				class="transform transition-transform {expanded ? 'rotate-180' : ''} text-gray-600 dark:text-gray-400"
			>
				<path
					d="m6 9 6 6 6-6"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
		</button>
	</div>

	<!-- Collapsible content -->
	{#if expanded}
		<div transition:slide={{ duration: 300, easing: quintOut }}>
			<div class="p-3">
				<FileBrowser {chatId} height="350px" />
			</div>
		</div>
	{/if}
</div>

<style>
	.file-browser-panel {
		background: white;
	}
	
	:global(.dark) .file-browser-panel {
		background: #1f2937;
	}
</style>