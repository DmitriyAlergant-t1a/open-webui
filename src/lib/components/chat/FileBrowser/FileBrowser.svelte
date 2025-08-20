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
	let api;

	// Custom RestDataProvider class that adds Authorization header
	class AuthenticatedRestDataProvider extends RestDataProvider {

		token: string;
		url: string;

		constructor(baseUrl: string, token: string) {
			super(baseUrl);
			this.token = token;
			this.url = baseUrl;
		}

		loadFiles(id: string = ''): Promise<any[]> {
			console.log("AuthenticatedRestDataProvider.loadFiles", id);
			return super.loadFiles(id);
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
		if (!chatId || !localStorage?.token) return null;
		
		// Create the provider pointing to our sandbox API with authentication
		const baseUrl = `http://localhost:8080/api/v1/sandboxes/${chatId}`;
		restProvider = new AuthenticatedRestDataProvider(baseUrl, localStorage.token);
		
		return restProvider;
	}

	// Handle dynamic folder loading (lazy loading)
	function handleRequestData(ev) {
		console.log('🔍 FOLDER REQUEST EVENT TRIGGERED:', ev);
		console.log('🔍 Event ID:', ev.id);
		console.log('🔍 RestProvider available:', !!restProvider);
		console.log('🔍 API available:', !!api);
		
		if (!restProvider || !api) {
			console.error('❌ RestDataProvider or API not available');
			return;
		}
		
		// Fetch folder contents from server
		const folderId = ev.id;
		const encodedId = encodeURIComponent(folderId);
		
		console.log('🌐 Making API call for folder:', folderId);
		console.log('🌐 URL:', `${restProvider.url}/files?id=${encodedId}`);
		
		// Use fetch directly since RestDataProvider's loadFiles doesn't support query params
		const url = `${restProvider.url}/files?id=${encodedId}`;
		fetch(url, {
			headers: {
				'Authorization': `Bearer ${restProvider.token}`
			}
		})
			.then(response => {
				console.log('📡 Response status:', response.status);
				return response.json();
			})
			.then((folderData) => {
				console.log('✅ Loaded folder data:', folderData);
				// Provide the data back to the filemanager
				api.exec("provide-data", { data: folderData, id: folderId });
				console.log('📤 Data provided back to filemanager');
			})
			.catch((error) => {
				console.error('❌ Error loading folder data:', error);
				toast.error('Failed to load folder contents');
			});
	}

	// Initialize the FileManager and connect RestDataProvider
	function init(api) {
		console.log('Initializing FileManager API');
		api = api; // Store API reference for dynamic loading
		
		restProvider = initializeProvider();

		api.setNext(restProvider);

		Promise.all([restProvider.loadFiles(), restProvider.loadInfo()]).then(([files, info]) => {
			data = files;
			drive = info.stats;
		});

		console.log('RestDataProvider connected to FileManager');

		// Add event handlers for file operations
		api.on("download-file", async (ev) => {
			try {
				const fileId = ev.id.startsWith('/') ? ev.id.substring(1) : ev.id;
				const downloadUrl = `http://localhost:8080/api/v1/sandboxes/${chatId}/files/${encodeURIComponent(fileId)}`;
				
				const response = await fetch(downloadUrl, {
					headers: {
						'Authorization': `Bearer ${localStorage.token}`
					}
				});
				
				if (!response.ok) {
					throw new Error(`Download failed: ${response.statusText}`);
				}
				
				const blob = await response.blob();
				const url = window.URL.createObjectURL(blob);
				const filename = fileId.split('/').pop() || 'download';
				
				const link = document.createElement('a');
				link.href = url;
				link.download = filename;
				link.style.display = 'none';
				document.body.appendChild(link);
				link.click();
				document.body.removeChild(link);
				window.URL.revokeObjectURL(url);
			} catch (error) {
				console.error('Download error:', error);
				toast.error('Failed to download file');
			}
		});

		api.on("open-file", async (ev) => {
			try {
				const fileId = ev.id.startsWith('/') ? ev.id.substring(1) : ev.id;
				const openUrl = `http://localhost:8080/api/v1/sandboxes/${chatId}/files/${encodeURIComponent(fileId)}`;
				
				const response = await fetch(openUrl, {
					headers: {
						'Authorization': `Bearer ${localStorage.token}`
					}
				});
				
				if (!response.ok) {
					throw new Error(`Open failed: ${response.statusText}`);
				}
				
				const blob = await response.blob();
				const url = window.URL.createObjectURL(blob);
				window.open(url, '_blank');
			} catch (error) {
				console.error('Open error:', error);
				toast.error('Failed to open file');
			}
		});
	}

	// Load initial data using RestDataProvider
	async function loadData() {
		if (!chatId || !localStorage?.token) {
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
			
			// Mark all folders as lazy for dynamic loading
			data = (files || []).map(item => ({
				...item,
				lazy: item.type === "folder" ? true : undefined
			}));
			drive = info?.stats || { used: 0, total: 0 };
			
			console.log('📂 Data loaded successfully:', { files: data, drive });
			console.log('📂 Folders marked as lazy:', data.filter(item => item.lazy).map(item => item.id));
			
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

	// Reload data when chatId changes
	$: if (chatId) {
		restProvider = null; // Reset provider for new chat
		loadData();
	}
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
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