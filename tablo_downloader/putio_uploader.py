#!/usr/bin/env python3
"""
Put.io uploader for Tablo recordings.
Uploads video files from the recordings directory to put.io, tracking what has been uploaded.
"""

import os
import json
import logging
import argparse
from pathlib import Path
import requests
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class PutIOUploader:
    """Handles uploading files to put.io and tracking upload status."""
    
    def __init__(self, token: str, db_path: str = "/data/putio_uploads.json"):
        """
        Initialize the uploader.
        
        Args:
            token: Put.io OAuth token
            db_path: Path to the upload tracking database
        """
        self.token = token
        self.db_path = Path(db_path)
        self.base_url = "https://upload.put.io/v2/files/upload"
        self.uploaded_files = self._load_upload_db()
    
    def _load_upload_db(self) -> Set[str]:
        """Load the list of already uploaded files."""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    return set(data.get('uploaded_files', []))
            except Exception as e:
                logger.warning(f"Could not load upload database: {e}")
        return set()
    
    def _save_upload_db(self):
        """Save the list of uploaded files."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_path, 'w') as f:
                json.dump({'uploaded_files': list(self.uploaded_files)}, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save upload database: {e}")
    
    def _is_video_file(self, filepath: Path) -> bool:
        """Check if a file is a video file based on extension."""
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.mpg', '.mpeg'}
        return filepath.suffix.lower() in video_extensions
    
    def upload_file(self, filepath: Path, parent_id: int = 0) -> bool:
        """
        Upload a single file to put.io.
        
        Args:
            filepath: Path to the file to upload
            parent_id: Parent folder ID on put.io (0 for root)
        
        Returns:
            True if upload was successful, False otherwise
        """
        try:
            # Check file size
            file_size = filepath.stat().st_size
            if file_size == 0:
                logger.warning(f"Skipping empty file: {filepath}")
                return False
            
            logger.info(f"Uploading {filepath.name} ({file_size / (1024**2):.2f} MB)...")
            
            # Create multipart upload
            with open(filepath, 'rb') as f:
                files = {'file': (filepath.name, f)}
                data = {
                    'oauth_token': self.token,
                    'parent_id': parent_id
                }
                
                response = requests.post(self.base_url, files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'OK':
                        logger.info(f"Successfully uploaded: {filepath.name}")
                        return True
                    else:
                        logger.error(f"Upload failed for {filepath.name}: {result}")
                        return False
                else:
                    logger.error(f"Upload failed for {filepath.name}: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error uploading {filepath}: {e}")
            return False
    
    def upload_newest(self, directory: Path, dry_run: bool = False) -> Dict[str, List[str]]:
        """
        Upload only the newest video file from a directory if it hasn't been uploaded yet.
        
        Args:
            directory: Directory containing video files
            dry_run: If True, only show what would be uploaded without actually uploading
        
        Returns:
            Dictionary with 'uploaded', 'skipped', and 'failed' lists
        """
        results = {
            'uploaded': [],
            'skipped': [],
            'failed': []
        }
        
        if not directory.exists():
            logger.error(f"Directory does not exist: {directory}")
            return results
        
        # Find all video files
        video_files = []
        for filepath in directory.iterdir():
            if filepath.is_file() and self._is_video_file(filepath):
                video_files.append(filepath)
        
        if not video_files:
            logger.info(f"No video files found in {directory}")
            return results
        
        # Sort by modification time, newest first
        video_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        newest_file = video_files[0]
        
        logger.info(f"Found {len(video_files)} video files. Newest: {newest_file.name}")
        
        rel_path = str(newest_file.relative_to(directory))
        
        # Check if already uploaded
        if rel_path in self.uploaded_files:
            logger.info(f"Newest file already uploaded: {newest_file.name}")
            results['skipped'].append(rel_path)
            return results
        
        if dry_run:
            logger.info(f"Would upload newest file: {newest_file.name}")
            results['uploaded'].append(rel_path)
        else:
            # Actually upload the file
            if self.upload_file(newest_file):
                self.uploaded_files.add(rel_path)
                self._save_upload_db()
                results['uploaded'].append(rel_path)
                logger.info(f"Successfully uploaded newest file: {newest_file.name}")
            else:
                results['failed'].append(rel_path)
                logger.error(f"Failed to upload newest file: {newest_file.name}")
        
        return results
    
    def upload_directory(self, directory: Path, dry_run: bool = False) -> Dict[str, List[str]]:
        """
        Upload all video files from a directory that haven't been uploaded yet.
        
        Args:
            directory: Directory containing video files
            dry_run: If True, only show what would be uploaded without actually uploading
        
        Returns:
            Dictionary with 'uploaded', 'skipped', and 'failed' lists
        """
        results = {
            'uploaded': [],
            'skipped': [],
            'failed': []
        }
        
        if not directory.exists():
            logger.error(f"Directory does not exist: {directory}")
            return results
        
        # Find all video files
        video_files = []
        for filepath in directory.iterdir():
            if filepath.is_file() and self._is_video_file(filepath):
                video_files.append(filepath)
        
        logger.info(f"Found {len(video_files)} video files in {directory}")
        
        for filepath in sorted(video_files):
            rel_path = str(filepath.relative_to(directory))
            
            # Check if already uploaded
            if rel_path in self.uploaded_files:
                logger.info(f"Skipping already uploaded: {filepath.name}")
                results['skipped'].append(rel_path)
                continue
            
            if dry_run:
                logger.info(f"Would upload: {filepath.name}")
                results['uploaded'].append(rel_path)
            else:
                # Actually upload the file
                if self.upload_file(filepath):
                    self.uploaded_files.add(rel_path)
                    self._save_upload_db()
                    results['uploaded'].append(rel_path)
                else:
                    results['failed'].append(rel_path)
        
        return results


def main():
    """Main entry point for the put.io uploader."""
    parser = argparse.ArgumentParser(description='Upload Tablo recordings to put.io')
    parser.add_argument('--token', required=True, help='Put.io OAuth token')
    parser.add_argument('--recordings-dir', default='/data/recordings',
                        help='Directory containing recordings (default: /data/recordings)')
    parser.add_argument('--db-path', default='/data/putio_uploads.json',
                        help='Path to upload tracking database (default: /data/putio_uploads.json)')
    parser.add_argument('--newest-only', action='store_true',
                        help='Upload only the newest video file (if not already uploaded)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be uploaded without actually uploading')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create uploader and process files
    uploader = PutIOUploader(token=args.token, db_path=args.db_path)
    recordings_dir = Path(args.recordings_dir)
    
    logger.info(f"Starting put.io upload from {recordings_dir}")
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will actually be uploaded")
    
    if args.newest_only:
        logger.info("Uploading only the newest video file")
        results = uploader.upload_newest(recordings_dir, dry_run=args.dry_run)
    else:
        results = uploader.upload_directory(recordings_dir, dry_run=args.dry_run)
    
    # Print summary
    print("\n=== Upload Summary ===")
    print(f"Uploaded: {len(results['uploaded'])} files")
    print(f"Skipped (already uploaded): {len(results['skipped'])} files")
    print(f"Failed: {len(results['failed'])} files")
    
    if results['uploaded']:
        print("\nUploaded files:")
        for f in results['uploaded']:
            print(f"  - {f}")
    
    if results['failed']:
        print("\nFailed uploads:")
        for f in results['failed']:
            print(f"  - {f}")
    
    return 0 if not results['failed'] else 1


if __name__ == '__main__':
    exit(main())