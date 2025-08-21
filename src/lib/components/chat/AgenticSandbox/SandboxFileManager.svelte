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
			console.log("AuthenticatedRestDataProvider.loadFiles(id=", id, ")");
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

	// Initialize the FileManager and connect RestDataProvider
	function init(fileManagerApi) {
		console.log('SandboxFileManager init(api)...');

		api = fileManagerApi;
		
        if (!restProvider) {
            restProvider = initializeProvider();
        }
        
        if (!restProvider) {
            console.error('Failed to initialize RestDataProvider');
            return;
        }
		api.setNext(restProvider);

		console.log('RestDataProvider connected to FileManager api');

		api.on("download-file", async (ev) => {
			try {
				const fileId = ev.id.startsWith('/') ? ev.id.substring(1) : ev.id;
				const downloadUrl = `/api/v1/sandboxes/${chatId}/files/${encodeURIComponent(fileId)}`;
				
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
				const openUrl = `/api/v1/sandboxes/${chatId}/files/${encodeURIComponent(fileId)}`;
				
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

		api.on("request-data", async (ev) => {
			console.log("request-data event received: ", ev);
			await loadDataForFolder(ev);
		});
	}

	// Load filesystem data for initial mount
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

			console.log('Loading initial files and drive info');

			await Promise.all([restProvider.loadFiles(""), restProvider.loadInfo()]).then(([files, info]) => {
				// Ensure files is always an array and has correct date objects
				data = Array.isArray(files) ? files : [];
				drive = info && info.stats ? info.stats : { used: 0, total: 0 };
			});

			console.log('📂 Initial data loaded successfully:', { files: data, drive });
			console.log('📂 Folders marked as lazy:', data.filter(item => item.lazy).map(item => item.id));
		} catch (error) {
			console.error('Failed to load initial data:', error);
			toast.error('Failed to load file browser data');
			data = [];
			drive = { used: 0, total: 0 };
		}
	}

	// Load data for a specific folder when requested by the file manager
	async function loadDataForFolder(ev) {
		const nodeId = ev.id || "";
		
		if (!chatId || !localStorage?.token) {
			console.warn('Cannot load folder data: missing chatId or user token');
			return;
		}

		if (!restProvider) {
			restProvider = initializeProvider();
		}
		
		if (!restProvider) {
			console.error('Failed to initialize RestDataProvider for folder loading');
			return;
		}

		try {
			console.log('Loading folder data for nodeId: ', nodeId);
			
			const folderData = await restProvider.loadFiles(nodeId);
			const processedData = Array.isArray(folderData) ? folderData : [];
			
			console.log('📂 Folder data loaded, providing to API:', { nodeId, data: processedData });
			
			// Provide the data to the file manager
			api.exec("provide-data", { 
				id: nodeId, 
				data: processedData 
			});
			
		} catch (error) {
			console.error('Failed to load folder data:', error);
			toast.error('Failed to load folder contents');
		}
	}

	onMount(() => {
		loadData();
	});

	// Reload data when chatId changes
	// $: if (chatId) {
	// 	api.exec("request-data", {
	// 		id: "/",
	// 	});
	// }
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
		border: none;
		border-radius: 24px;
		overflow: hidden;
	}
	
	/* Fix for Files label wrapping */
	.file-browser-container :global(.wx-name) {
		white-space: nowrap;
	}
</style>