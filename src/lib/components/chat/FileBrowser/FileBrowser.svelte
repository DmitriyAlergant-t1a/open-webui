<script lang="ts">
	import { onMount } from 'svelte';
	import { Filemanager, Willow } from 'wx-svelte-filemanager';
	import {
		getSandboxFiles,
		uploadSandboxFile,
		deleteSandboxFile,
		createSandboxFolder,
		renameSandboxFile,
		downloadSandboxFile,
		type FileItem
	} from '$lib/apis/sandboxes';
	import { user } from '$lib/stores';
	import { toast } from 'svelte-sonner';

	export let chatId: string;
	export let height: string = '400px';

	let files: FileItem[] = [];
	let loading = false;
	
	async function loadFiles(path: string = '') {
		if (!$user?.token || !chatId) return;

		loading = true;
		try {
			console.log('Loading files for path:', path);
			const result = await getSandboxFiles($user.token, chatId, path);
			files = result || [];
		} catch (error) {
			console.error('Failed to load files:', error);
			files = [];
		} finally {
			loading = false;
		}
	}
	
	// Convert our FileItem format to SVAR format
	$: svarData = Array.isArray(files) ? files.map(file => {
		const fileName = file.name || file.id.split('/').pop() || file.id;
		return {
			id: `/${fileName}`,
			size: file.size,
			date: new Date(parseFloat(file.date) * 1000),
			type: file.type
		};
	}) : [];

	onMount(() => {
		loadFiles();
	});
	
	// Create API configuration for SVAR FileManager
	let api = {
		read: async (path = '') => {
			console.log('SVAR API: read called with path:', path);
			if (!$user?.token || !chatId) return [];
			
			try {
				const result = await getSandboxFiles($user.token, chatId, path);
				return Array.isArray(result) ? result.map(file => {
					const fileName = file.name || file.id.split('/').pop() || file.id;
					return {
						id: `/${fileName}`,
						size: file.size,
						date: new Date(parseFloat(file.date) * 1000),
						type: file.type
					};
				}) : [];
			} catch (error) {
				console.error('SVAR API read error:', error);
				return [];
			}
		},
		
		upload: async (file, path = '') => {
			console.log('SVAR API: upload called', { file, path });
			if (!$user?.token || !chatId) throw new Error('No authentication');
			
			await uploadSandboxFile($user.token, chatId, file, path);
			return { success: true };
		},
		
		remove: async (id) => {
			console.log('SVAR API: remove called with id:', id);
			if (!$user?.token || !chatId) throw new Error('No authentication');
			
			// Convert the id back to a path for our API
			const filePath = id.startsWith('/') ? id.substring(1) : id;
			await deleteSandboxFile($user.token, chatId, filePath);
			return { success: true };
		},
		
		createFolder: async (name, path = '') => {
			console.log('SVAR API: createFolder called', { name, path });
			if (!$user?.token || !chatId) throw new Error('No authentication');
			
			await createSandboxFolder($user.token, chatId, name, path);
			return { success: true };
		}
	};

	// We no longer need manual loading since SVAR handles it via the API
</script>

<div class="file-browser-container" style="height: {height};">
	<Willow>
		<Filemanager
			data={svarData}
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