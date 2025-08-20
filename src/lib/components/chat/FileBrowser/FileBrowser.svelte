<script lang="ts">
	import { onMount } from 'svelte';
	import { RestDataProvider } from 'wx-filemanager-data-provider';
	import { Filemanager, Willow } from 'wx-svelte-filemanager';
	import { user } from '$lib/stores';
	import { toast } from 'svelte-sonner';

	export let chatId: string;
	export let height: string = '400px';

	let data = [];
	let drive = {};
	let restProvider;

	// Custom RestDataProvider class that adds Authorization header
	class AuthenticatedRestDataProvider extends RestDataProvider {

		token: string;

		constructor(baseUrl: string, token: string) {
			super(baseUrl);
			this.token = token;
		}
		
		send<T>(url: string, method: string, data: any, headers: Record<string, string> = {}): Promise<T> {
			const authHeaders = {
				...headers,
				'Authorization': `Bearer ${this.token}`
			};
			
			return super.send<T>(url, method, data, authHeaders);
		}
	}

	// Initialize RestDataProvider with backend URL and authentication
	function initializeProvider() {
		if (!chatId || !$user?.token) return null;
		
		// Create the provider pointing to our sandbox API with authentication
		const baseUrl = `http://localhost:8080/api/v1/sandboxes/${chatId}`;
		restProvider = new AuthenticatedRestDataProvider(baseUrl, $user.token);
		
		return restProvider;
	}

	// Initialize the FileManager and connect RestDataProvider
	function init(api) {
		console.log('Initializing FileManager API');
		
		if (!restProvider) {
			restProvider = initializeProvider();
		}
		
		if (restProvider && api) {
			api.setNext(restProvider);
			console.log('RestDataProvider connected to FileManager');
		}
	}

	// Load initial data using RestDataProvider
	async function loadData() {
		if (!chatId || !$user?.token) {
			console.warn('Cannot load data: missing chatId or user token');
			return;
		}

		try {
			if (!restProvider) {
				restProvider = initializeProvider();
			}
			
			if (!restProvider) {
				console.error('Failed to initialize RestDataProvider');
				return;
			}

			console.log('Loading files and drive info...');
			
			// Load both files and drive info in parallel
			const [files, info] = await Promise.all([
				restProvider.loadFiles(),
				restProvider.loadInfo()
			]);
			
			data = files || [];
			drive = info?.stats || { used: 0, total: 0 };
			
			console.log('Data loaded successfully:', { files: data, drive });
			
		} catch (error) {
			console.error('Failed to load data:', error);
			toast.error('Failed to load file browser data');
			data = [];
			drive = { used: 0, total: 0 };
		}
	}

	// Initialize when component mounts
	onMount(() => {
		loadData();
	});

	// Reload data when chatId or user token changes
	$: if (chatId || $user?.token) {
		restProvider = null; // Reset provider for new chat or token change
		loadData();
	}
</script>

<div
    class="file-browser-container sticky-top"
    style="height: {height}; z-index: 9000; position: sticky; top: 0;"
    on:dragenter={(e) => e.stopPropagation()}
    on:dragover={(e) => e.stopPropagation()}
    on:drop={(e) => e.stopPropagation()}
>
	<Willow>
		<Filemanager
			{init}
			{data}
			{drive}
			mode={"table"}
		/>
	</Willow>
</div>

<style>
	.file-browser-container {
		width: 100%;
		border: 1px solid #e2e8f0;
		border-radius: 8px;
		overflow: hidden;
	}
</style>