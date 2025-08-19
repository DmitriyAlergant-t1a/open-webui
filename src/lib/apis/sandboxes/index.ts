import { WEBUI_API_BASE_URL } from '$lib/constants';

export interface FileItem {
	id: string;
	name: string;
	size: number;
	date: string;
	type: 'file' | 'folder';
	children?: FileItem[];
}

export interface SandboxInfo {
	used_bytes: number;
	file_count: number;
}

const handleResponse = async (res: Response) => {
	if (!res.ok) throw await res.json();
	return res.json();
};

const handleError = (err: any) => {
	console.error(err);
	throw err.detail || err.message || 'An error occurred';
};

export const getSandboxFiles = async (
	token: string,
	chatId: string,
	path: string = ''
): Promise<FileItem[]> => {
	try {
		const url = new URL(`${WEBUI_API_BASE_URL}/sandboxes/${chatId}/files`);
		if (path) {
			url.searchParams.append('path', path);
		}

		const res = await fetch(url.toString(), {
			method: 'GET',
			headers: {
				Accept: 'application/json',
				authorization: `Bearer ${token}`
			}
		});

		return await handleResponse(res);
	} catch (err) {
		handleError(err);
	}
};

export const uploadSandboxFile = async (
	token: string,
	chatId: string,
	file: File,
	path: string = ''
): Promise<any> => {
	try {
		const data = new FormData();
		data.append('file', file);
		if (path) {
			data.append('path', path);
		}

		const res = await fetch(`${WEBUI_API_BASE_URL}/sandboxes/${chatId}/files`, {
			method: 'POST',
			headers: {
				authorization: `Bearer ${token}`
			},
			body: data
		});

		return await handleResponse(res);
	} catch (err) {
		handleError(err);
	}
};

export const downloadSandboxFile = async (
	token: string,
	chatId: string,
	filePath: string
): Promise<Blob> => {
	try {
		const res = await fetch(`${WEBUI_API_BASE_URL}/sandboxes/${chatId}/files/${filePath}`, {
			method: 'GET',
			headers: {
				authorization: `Bearer ${token}`
			}
		});

		if (!res.ok) {
			const error = await res.json();
			throw error;
		}

		return await res.blob();
	} catch (err) {
		handleError(err);
	}
};

export const deleteSandboxFile = async (
	token: string,
	chatId: string,
	filePath: string
): Promise<any> => {
	try {
		const res = await fetch(`${WEBUI_API_BASE_URL}/sandboxes/${chatId}/files/${filePath}`, {
			method: 'DELETE',
			headers: {
				Accept: 'application/json',
				authorization: `Bearer ${token}`
			}
		});

		return await handleResponse(res);
	} catch (err) {
		handleError(err);
	}
};

export const createSandboxFolder = async (
	token: string,
	chatId: string,
	folderName: string,
	path: string = ''
): Promise<any> => {
	try {
		const url = new URL(`${WEBUI_API_BASE_URL}/sandboxes/${chatId}/folders`);
		url.searchParams.append('folder_name', folderName);
		if (path) {
			url.searchParams.append('path', path);
		}

		const res = await fetch(url.toString(), {
			method: 'POST',
			headers: {
				Accept: 'application/json',
				authorization: `Bearer ${token}`
			}
		});

		return await handleResponse(res);
	} catch (err) {
		handleError(err);
	}
};

export const renameSandboxFile = async (
	token: string,
	chatId: string,
	filePath: string,
	newName: string
): Promise<any> => {
	try {
		const url = new URL(`${WEBUI_API_BASE_URL}/sandboxes/${chatId}/files/${filePath}`);
		url.searchParams.append('new_name', newName);

		const res = await fetch(url.toString(), {
			method: 'PUT',
			headers: {
				Accept: 'application/json',
				authorization: `Bearer ${token}`
			}
		});

		return await handleResponse(res);
	} catch (err) {
		handleError(err);
	}
};

export const getSandboxInfo = async (
	token: string,
	chatId: string
): Promise<SandboxInfo> => {
	try {
		const res = await fetch(`${WEBUI_API_BASE_URL}/sandboxes/${chatId}/info`, {
			method: 'GET',
			headers: {
				Accept: 'application/json',
				authorization: `Bearer ${token}`
			}
		});

		return await handleResponse(res);
	} catch (err) {
		handleError(err);
	}
};