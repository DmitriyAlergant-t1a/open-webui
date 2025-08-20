import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Request
from pydantic import BaseModel

from open_webui.constants import ERROR_MESSAGES
from open_webui.models.chats import Chats
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

# Base directory for sandboxes
SANDBOX_BASE_PATH = Path("./data/sandboxes")


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


def build_file_tree(base_path: Path, relative_path: str = "") -> List[dict]:
    """Build file tree structure for the file manager in SVAR format"""
    items = []
    current_path = base_path / relative_path if relative_path else base_path
    
    if not current_path.exists():
        return items
    
    try:
        for item in current_path.iterdir():
            if item.is_file():
                stat = item.stat()
                # Format the id with leading slash for SVAR compatibility
                file_id = "/" + str(Path(relative_path) / item.name) if relative_path else "/" + item.name
                items.append({
                    "id": file_id,
                    "size": stat.st_size,
                    "date": stat.st_mtime * 1000,  # SVAR expects milliseconds
                    "type": "file"
                })
            elif item.is_dir():
                stat = item.stat()
                folder_id = "/" + str(Path(relative_path) / item.name) if relative_path else "/" + item.name
                items.append({
                    "id": folder_id,
                    "date": stat.st_mtime * 1000,  # SVAR expects milliseconds
                    "type": "folder",
                    "lazy": True  # Enable dynamic loading for folders
                })
    except PermissionError:
        log.warning(f"Permission denied accessing {current_path}")
    
    return sorted(items, key=lambda x: (x["type"] == "file", x["id"].lower()))


############################
# Sandbox File Operations
############################


@router.get("/{chat_id}/files")
@router.get("/{chat_id}/files/{folder_id:path}")
async def list_sandbox_files(
    chat_id: str,
    folder_id: str = None,
    id: str = "",  # RestDataProvider sends 'id' parameter for folder requests
    user=Depends(get_verified_user)
):
    """List files and folders in chat sandbox - compatible with RestDataProvider"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)

    print("Making sure sandbox path exists... ", sandbox_path)
    sandbox_path.mkdir(parents=True, exist_ok=True)
    
    # Handle both path parameter and query parameter approaches
    if folder_id is not None:
        # URL path approach: /files/testdir
        folder_path = folder_id
    else:
        # Query parameter approach: /files?id=/testdir
        folder_path = id.lstrip("/") if id else ""
    
    safe_path = sanitize_path(folder_path)
    return build_file_tree(sandbox_path, safe_path)


@router.post("/{chat_id}/upload")
async def upload_sandbox_file(
    chat_id: str,
    file: UploadFile = File(...),
    id: str = "",
    user=Depends(get_verified_user)
):
    """Upload a file to chat sandbox"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)
    sandbox_path.mkdir(parents=True, exist_ok=True)
    
    safe_path = sanitize_path(id.lstrip("/"))
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


@router.post("/{chat_id}/files/{path:path}")
async def create_file_or_folder(
    chat_id: str,
    path: str,
    request: Request,
    user=Depends(get_verified_user)
):
    """Create a new file or folder - compatible with RestDataProvider"""
    import json
    
    verify_chat_access(chat_id, user.id)
    
    # Get the request body to extract creation details
    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is required"
        )
    
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in request body"
        )
    
    name = data.get("name")
    item_type = data.get("type")
    
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'name' parameter is required"
        )
    
    if item_type not in ["file", "folder"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'type' must be either 'file' or 'folder'"
        )
    
    sandbox_path = get_sandbox_path(chat_id)
    sandbox_path.mkdir(parents=True, exist_ok=True)
    
    # Handle path parameter - remove leading slash and decode
    safe_path = sanitize_path(path.lstrip("/")) if path != "/" else ""
    target_dir = sandbox_path / safe_path if safe_path else sandbox_path
    
    new_item_path = target_dir / name
    
    try:
        if item_type == "folder":
            new_item_path.mkdir(parents=True, exist_ok=False)
            # Return folder info in SVAR format
            folder_id = "/" + str(new_item_path.relative_to(sandbox_path))
            stat = new_item_path.stat()
            return {
                "id": folder_id,
                "date": stat.st_mtime * 1000,
                "type": "folder",
                "lazy": True
            }
        else:  # file
            new_item_path.touch(exist_ok=False)
            # Return file info in SVAR format
            file_id = "/" + str(new_item_path.relative_to(sandbox_path))
            stat = new_item_path.stat()
            return {
                "id": file_id,
                "size": stat.st_size,
                "date": stat.st_mtime * 1000,
                "type": "file"
            }
    except FileExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{item_type.capitalize()} already exists"
        )
    except Exception as e:
        log.error(f"Error creating {item_type}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create {item_type}"
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
    request: Request,
    user=Depends(get_verified_user)
):
    """Rename a file or folder in chat sandbox - compatible with RestDataProvider"""
    import json
    
    verify_chat_access(chat_id, user.id)
    
    # Get the request body to extract the new name
    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is required"
        )
    
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in request body"
        )
    
    operation = data.get("operation")
    new_name = data.get("name")
    
    if operation != "rename":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only 'rename' operation is supported"
        )
    
    if not new_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'name' parameter must be provided"
        )
    
    sandbox_path = get_sandbox_path(chat_id)
    # Remove leading slash from file_path for compatibility
    safe_path = sanitize_path(file_path.lstrip("/"))
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
    
    # Calculate new path
    new_path = old_path.parent / new_name
    
    # Ensure new path is within sandbox
    try:
        new_path.resolve().relative_to(sandbox_path.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if new name already exists
    if new_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A file or folder with this name already exists"
        )
    
    try:
        # Perform the rename
        old_path.rename(new_path)
        
        # Return new file info in the format expected by RestDataProvider
        new_file_id = "/" + str(new_path.relative_to(sandbox_path))
        
        return {
            "result": {
                "id": new_file_id,
                "name": new_name
            }
        }
    except Exception as e:
        log.error(f"Error renaming {old_path} to {new_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rename file or folder"
        )


@router.get("/{chat_id}/info")
async def get_sandbox_info(
    chat_id: str,
    user=Depends(get_verified_user)
):
    """Get sandbox storage information - compatible with RestDataProvider"""
    verify_chat_access(chat_id, user.id)
    
    sandbox_path = get_sandbox_path(chat_id)
    
    if not sandbox_path.exists():
        return {"stats": {"used": 0, "total": 100000000}}  # 100MB default limit
    
    total_size = 0
    file_count = 0
    
    try:
        for item in sandbox_path.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
                file_count += 1
    except Exception as e:
        log.error(f"Error calculating sandbox info: {e}")
    
    # Return in format expected by RestDataProvider
    return {
        "stats": {
            "used": total_size,
            "total": 100000000  # 100MB limit, can be configurable
        }
    }