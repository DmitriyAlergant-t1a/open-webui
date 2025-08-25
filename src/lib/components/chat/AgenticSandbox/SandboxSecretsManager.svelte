<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { WEBUI_API_BASE_URL } from '$lib/constants';

	export let chatId: string;
	export let height: string = '350px';

	interface EnvVar {
		key: string;
		value: string;
	}

	let envVars: EnvVar[] = [];
	let loading = false;
	let saving = false;

	async function loadEnvVars() {
		if (!chatId || !localStorage?.token) {
			return;
		}

		loading = true;
		try {
			const response = await fetch(`${WEBUI_API_BASE_URL}/sandboxes/${chatId}/env`, {
				headers: {
					'Authorization': `Bearer ${localStorage.token}`
				}
			});

			if (!response.ok) {
				throw new Error(`Failed to load environment variables: ${response.statusText}`);
			}

			const data = await response.json();
			envVars = data.variables || [];
		} catch (error) {
			console.error('Error loading environment variables:', error);
			toast.error('Failed to load environment variables');
			envVars = [];
		} finally {
			loading = false;
		}
	}

	async function saveEnvVars() {
		if (!chatId || !localStorage?.token) {
			return;
		}

		saving = true;
		try {
			const response = await fetch(`${WEBUI_API_BASE_URL}/sandboxes/${chatId}/env`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${localStorage.token}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ variables: envVars })
			});

			if (!response.ok) {
				throw new Error(`Failed to save environment variables: ${response.statusText}`);
			}
		} catch (error) {
			console.error('Error saving environment variables:', error);
			toast.error('Failed to save environment variables');
		} finally {
			saving = false;
		}
	}

	function addEnvVar() {
		envVars = [...envVars, { key: '', value: '' }];
		// Don't auto-save empty variables
	}

	function removeEnvVar(index: number) {
		envVars = envVars.filter((_, i) => i !== index);
		// Only save if there are valid variables remaining, or if we need to clear everything
		const hasValidVars = envVars.some(env => env.key.trim() && env.value.trim());
		if (hasValidVars || envVars.length === 0) {
			saveEnvVars();
		}
	}

	function updateEnvVar(index: number, field: 'key' | 'value', value: string) {
		envVars[index][field] = value;
		envVars = envVars; // Trigger reactivity
		
		// Only save if both key and value are not empty
		const envVar = envVars[index];
		if (envVar.key.trim() && envVar.value.trim()) {
			// Debounced save
			clearTimeout(saveTimeout);
			saveTimeout = setTimeout(() => saveEnvVars(), 500);
		}
	}

	function isValidKey(key: string): boolean {
		if (!key) return true; // Allow empty for new entries
		return /^[A-Za-z_][A-Za-z0-9_]*$/.test(key);
	}

	let saveTimeout: any;

	onMount(() => {
		loadEnvVars();
	});

	// Reload when chatId changes
	$: if (chatId) {
		loadEnvVars();
	}
</script>

<div class="bg-white dark:bg-gray-700/90 rounded-xl border border-gray-200 dark:border-gray-600 p-4 flex flex-col gap-3 overflow-hidden" style="height: {height};">
	{#if loading}
		<div class="flex flex-col items-center justify-center gap-2 text-gray-500 flex-1 text-sm">
			<div class="w-5 h-5 border-2 border-gray-200 border-t-blue-500 rounded-full animate-spin"></div>
			<span>Loading...</span>
		</div>
	{:else}
		<div class="flex flex-col gap-2 flex-1 overflow-y-auto max-h-[calc(100%-60px)]">
			{#each envVars as envVar, index}
				<div class="flex gap-2 items-center py-1">
					<input
						type="text"
						bind:value={envVar.key}
						placeholder="KEY"
						class="flex-none w-30 px-2 py-1.5 border border-gray-300 dark:border-gray-500 rounded font-mono text-xs bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
						class:border-red-500={!isValidKey(envVar.key)}
						on:input={() => updateEnvVar(index, 'key', envVar.key)}
					/>
					<input
						type="text"
						bind:value={envVar.value}
						placeholder="value"
						class="flex-1 px-2 py-1.5 border border-gray-300 dark:border-gray-500 rounded font-mono text-xs bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
						on:input={() => updateEnvVar(index, 'value', envVar.value)}
					/>
					<button 
						class="p-1 border-0 bg-transparent text-gray-500 cursor-pointer rounded flex items-center justify-center transition-all duration-200 flex-shrink-0 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-500/10 dark:hover:text-red-400" 
						on:click={() => removeEnvVar(index)} 
						title="Remove"
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<line x1="18" y1="6" x2="6" y2="18"></line>
							<line x1="6" y1="6" x2="18" y2="18"></line>
						</svg>
					</button>
				</div>
			{/each}
			
			{#if envVars.length === 0}
				<div class="py-6 text-center text-gray-400 flex-1 flex items-center justify-center">
					<p class="text-sm">No environment variables</p>
				</div>
			{/if}
		</div>

		<button class="px-3 py-2 border border-dashed border-gray-300 dark:border-gray-500 rounded-md bg-transparent text-gray-500 dark:text-gray-400 cursor-pointer flex items-center justify-center gap-1.5 text-xs transition-all duration-200 mt-auto hover:border-blue-500 hover:text-blue-500 hover:bg-blue-50 dark:hover:border-blue-400 dark:hover:text-blue-400 dark:hover:bg-blue-500/10" on:click={addEnvVar}>
			<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<line x1="12" y1="5" x2="12" y2="19"></line>
				<line x1="5" y1="12" x2="19" y2="12"></line>
			</svg>
			Add Environment Variable (for secrets)
		</button>

		{#if saving}
			<div class="absolute top-2 right-2 flex items-center gap-1.5 text-xs text-gray-500 bg-white dark:bg-gray-700 px-2 py-1 rounded border border-gray-200 dark:border-gray-600">
				<div class="w-3 h-3 border border-gray-200 border-t-blue-500 rounded-full animate-spin"></div>
				Saving...
			</div>
		{/if}
	{/if}
</div>

<style>
	/* Minimal styles for container positioning that can't be easily replaced with Tailwind */
</style>