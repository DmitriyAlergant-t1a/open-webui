import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel

from open_webui.constants import ERROR_MESSAGES
from open_webui.models.chats import Chats
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

# Base directory for sandboxes
SANDBOX_BASE_PATH = Path("./backend/data/sandboxes")


class FileItem(BaseModel):
    id: str
    name: str
    size: int
    date: str
    type: str  # "file" or "folder"
    children: Optional[List["FileItem"]] = None


class SandboxInfo(BaseModel):
    used_bytes: int
    file_count: int


def sanitize_path(path: str) -> str:
    """Sanitize path to prevent directory traversal"""
    # Remove leading/trailing slashes and decode URL encoding
    path = unquote(path).strip("/")
    
    # Remove any .. components to prevent directory traversal
    path_parts = []
    for part in path.split("/"):
        if part and part != "." and part != "..":
            path_parts.append(part)
    
    return "/".join(path_parts)


def get_sandbox_path(chat_id: str) -> Path:
    """Get the sandbox directory path for a chat"""
    return SANDBOX_BASE_PATH / chat_id


def verify_chat_access(chat_id: str, user_id: str) -> None:
    """Verify that user has access to the chat"""
    chat = Chats.get_chat_by_id_and_user_id(chat_id, user_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found or access denied"
        )


def build_file_tree(base_path: Path, relative_path: str = "") -> List[FileItem]:
    """Build file tree structure for the file manager"""
    items = []
    current_path = base_path / relative_path if relative_path else base_path
    
    if not current_path.exists():
        return items
    
    try:
        for item in current_path.iterdir():
            if item.is_file():
                stat = item.stat()
                items.append(FileItem(
                    id=str(Path(relative_path) / item.name) if relative_path else item.name,
                    name=item.name,
                    size=stat.st_size,
                    date=str(stat.st_mtime),
                    type="file"
                ))
            elif item.is_dir():
                stat = item.stat()
                items.append(FileItem(
                    id=str(Path(relative_path) / item.name) if relative_path else item.name,
                    name=item.name,
                    size=0,
                    date=str(stat.st_mtime),
                    type="folder",
                    children=[]
                ))
    except PermissionError:
        log.warning(f"Permission denied accessing {current_path}")
    
    return sorted(items, key=lambda x: (x.type == "file", x.name.lower()))


############################
# Sandbox File Operations
############################


@router.get("/{chat_id}/files", response_model=List[FileItem])
async def list_sandbox_files(
    chat_id: str,
    path: str = "",
    user=Depends(get_verified_user)
):
    """List files and folders in chat sandbox"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)
    sandbox_path.mkdir(parents=True, exist_ok=True)
    
    safe_path = sanitize_path(path)
    return build_file_tree(sandbox_path, safe_path)


@router.post("/{chat_id}/files")
async def upload_sandbox_file(
    chat_id: str,
    file: UploadFile = File(...),
    path: str = "",
    user=Depends(get_verified_user)
):
    """Upload a file to chat sandbox"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)
    sandbox_path.mkdir(parents=True, exist_ok=True)
    
    safe_path = sanitize_path(path)
    target_dir = sandbox_path / safe_path if safe_path else sandbox_path
    target_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = target_dir / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"message": "File uploaded successfully", "filename": file.filename}
    except Exception as e:
        log.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )


@router.get("/{chat_id}/files/{file_path:path}")
async def download_sandbox_file(
    chat_id: str,
    file_path: str,
    user=Depends(get_verified_user)
):
    """Download a file from chat sandbox"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)
    safe_path = sanitize_path(file_path)
    target_file = sandbox_path / safe_path
    
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Ensure file is within sandbox
    try:
        target_file.resolve().relative_to(sandbox_path.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=target_file,
        filename=target_file.name,
        media_type='application/octet-stream'
    )


@router.delete("/{chat_id}/files/{file_path:path}")
async def delete_sandbox_file(
    chat_id: str,
    file_path: str,
    user=Depends(get_verified_user)
):
    """Delete a file or folder from chat sandbox"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)
    safe_path = sanitize_path(file_path)
    target_path = sandbox_path / safe_path
    
    if not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File or folder not found"
        )
    
    # Ensure path is within sandbox
    try:
        target_path.resolve().relative_to(sandbox_path.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    try:
        if target_path.is_file():
            target_path.unlink()
        else:
            shutil.rmtree(target_path)
        
        return {"message": "Deleted successfully"}
    except Exception as e:
        log.error(f"Error deleting {target_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete"
        )


@router.post("/{chat_id}/folders")
async def create_sandbox_folder(
    chat_id: str,
    folder_name: str,
    path: str = "",
    user=Depends(get_verified_user)
):
    """Create a new folder in chat sandbox"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)
    sandbox_path.mkdir(parents=True, exist_ok=True)
    
    safe_path = sanitize_path(path)
    target_dir = sandbox_path / safe_path if safe_path else sandbox_path
    
    new_folder = target_dir / folder_name
    
    try:
        new_folder.mkdir(parents=True, exist_ok=False)
        return {"message": "Folder created successfully", "folder_name": folder_name}
    except FileExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Folder already exists"
        )
    except Exception as e:
        log.error(f"Error creating folder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create folder"
        )


@router.put("/{chat_id}/files/{file_path:path}")
async def rename_sandbox_file(
    chat_id: str,
    file_path: str,
    new_name: str,
    user=Depends(get_verified_user)
):
    """Rename a file or folder in chat sandbox"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)
    safe_path = sanitize_path(file_path)
    old_path = sandbox_path / safe_path
    
    if not old_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File or folder not found"
        )
    
    # Ensure old path is within sandbox
    try:
        old_path.resolve().relative_to(sandbox_path.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    new_path = old_path.parent / new_name
    
    if new_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Target name already exists"
        )
    
    try:
        old_path.rename(new_path)
        return {"message": "Renamed successfully", "new_name": new_name}
    except Exception as e:
        log.error(f"Error renaming {old_path} to {new_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rename"
        )


@router.get("/{chat_id}/info", response_model=SandboxInfo)
async def get_sandbox_info(
    chat_id: str,
    user=Depends(get_verified_user)
):
    """Get sandbox storage information"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)
    
    if not sandbox_path.exists():
        return SandboxInfo(used_bytes=0, file_count=0)
    
    total_size = 0
    file_count = 0
    
    try:
        for item in sandbox_path.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
                file_count += 1
    except Exception as e:
        log.error(f"Error calculating sandbox info: {e}")
    
    return SandboxInfo(used_bytes=total_size, file_count=file_count)