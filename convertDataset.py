import os
import shutil
import argparse
import json
from pathlib import Path

def merge_json_files(existing_file_path, new_file_path, dest_path):
    """Merge two JSON files by combining their content."""
    try:
        # Read existing JSON
        with open(existing_file_path, 'r') as existing_file:
            existing_data = json.load(existing_file)
        
        # Read new JSON
        with open(new_file_path, 'r') as new_file:
            new_data = json.load(new_file)
        
        # Merge the data
        if isinstance(existing_data, dict) and isinstance(new_data, dict):
            # For dictionaries, merge keys
            merged_data = existing_data.copy()
            merged_data.update(new_data)
        elif isinstance(existing_data, list) and isinstance(new_data, list):
            # For lists, combine and remove duplicates
            merged_data = existing_data + [item for item in new_data if item not in existing_data]
        else:
            # If types don't match, keep existing and add new as separate entry
            merged_data = {"existing": existing_data, "new": new_data}
        
        # Write merged JSON
        with open(dest_path, 'w') as dest_file:
            json.dump(merged_data, dest_file, indent=2)
        
        return True
    except (json.JSONDecodeError, Exception) as e:
        print(f"  Error merging JSON: {e}")
        return False

def merge_text_files(existing_file_path, new_file_path, dest_path):
    """Append new file content to existing file, avoiding duplicates."""
    # Read the existing content
    with open(existing_file_path, 'r') as existing_file:
        existing_content = existing_file.read()
    
    # Read the new content to append
    with open(new_file_path, 'r') as new_file:
        new_content = new_file.read()
    
    # Split content into lines for duplicate checking
    existing_lines = set(line.strip() for line in existing_content.splitlines() if line.strip())
    new_lines = [line.strip() for line in new_content.splitlines() if line.strip()]
    
    # Filter out duplicates - only keep new lines that aren't already present
    unique_new_lines = [line for line in new_lines if line not in existing_lines]
    
    # Write combined content to destination
    with open(dest_path, 'w') as dest_file:
        # Write existing content
        dest_file.write(existing_content)
        
        # Add newline if the existing content doesn't end with one and we have new content
        if existing_content and not existing_content.endswith('\n') and unique_new_lines:
            dest_file.write('\n')
        
        # Write only the unique new content
        if unique_new_lines:
            dest_file.write('\n'.join(unique_new_lines))
            dest_file.write('\n')  # End with newline

def combine_folders(source_folder, destination_folder, merge_mode=True):
    """
    Copy/merge source folder into destination folder.
    
    Args:
        source_folder (str): Path to source folder to copy from
        destination_folder (str): Path to destination folder (folder2)
        merge_mode (bool): If True, merge text files with same names (default: True)
    """
    
    # Create destination folder if it doesn't exist
    os.makedirs(destination_folder, exist_ok=True)
    
    print(f"Copying folder1 into folder2 (merge_mode={merge_mode}):")
    print(f"  Source (folder1): {source_folder}")
    print(f"  Destination (folder2): {destination_folder}")
    print(f"  Text files will be merged, images/labels will be overwritten")
    
    total_files = 0
    merged_files = 0
    
    # Track existing files in destination (folder2)
    existing_files = {}
    if os.path.exists(destination_folder):
        for root, dirs, files in os.walk(destination_folder):
            for file in files:
                existing_file = os.path.join(root, file)
                rel_path = os.path.relpath(existing_file, destination_folder)
                existing_files[rel_path] = existing_file
    
    # Copy/merge files from source folder (folder1) into destination (folder2)
    if os.path.exists(source_folder):
        print(f"\nCopying from {source_folder}...")
        for root, dirs, files in os.walk(source_folder):
            for file in files:
                source_file = os.path.join(root, file)
                rel_path = os.path.relpath(source_file, source_folder)
                dest_file = os.path.join(destination_folder, rel_path)
                
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                
                if rel_path in existing_files:
                    # File exists in destination
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext == '.json':
                        # JSON file - merge intelligently
                        try:
                            print(f"  Merging JSON: {file}")
                            if merge_json_files(existing_files[rel_path], source_file, dest_file):
                                merged_files += 1
                            else:
                                # Fallback to overwrite
                                print(f"  Overwriting: {file}")
                                shutil.copy2(source_file, dest_file)
                        except Exception as e:
                            print(f"  Error merging JSON {file}: {e}")
                            print(f"  Overwriting: {file}")
                            shutil.copy2(source_file, dest_file)
                    elif file_ext in ['.txt', '.py', '.xml', '.csv', '.log']:
                        # Text file - merge line by line
                        try:
                            print(f"  Merging: {file}")
                            merge_text_files(existing_files[rel_path], source_file, dest_file)
                            merged_files += 1
                        except Exception as e:
                            print(f"  Error merging {file}: {e}")
                            # Fallback to overwrite
                            print(f"  Overwriting: {file}")
                            shutil.copy2(source_file, dest_file)
                    else:
                        # Binary file (image/label) - overwrite
                        print(f"  Overwriting: {file}")
                        shutil.copy2(source_file, dest_file)
                else:
                    # New file - just copy
                    print(f"  Copied: {file}")
                    shutil.copy2(source_file, dest_file)
                
                total_files += 1
    else:
        print(f"Warning: Source folder does not exist: {source_folder}")
    
    print(f"\nCombining complete!")
    print(f"Total files processed: {total_files}")
    if merge_mode:
        print(f"Files merged: {merged_files}")

def main():
    parser = argparse.ArgumentParser(description='Copy folder1 into folder2 (folder2 becomes destination)')
    parser.add_argument('folder1', help='Path to source folder (will be copied into folder2)')
    parser.add_argument('folder2', help='Path to destination folder (folder1 will be copied here)')
    parser.add_argument('--merge', action='store_true', help='Merge text files with same names')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be copied without actually copying')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN - No files will be copied")
        if os.path.exists(args.folder1):
            print(f"\nFiles in {args.folder1} (source):")
            for root, dirs, files in os.walk(args.folder1):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), args.folder1)
                    print(f"  {rel_path}")
        if os.path.exists(args.folder2):
            print(f"\nExisting files in {args.folder2} (destination):")
            for root, dirs, files in os.walk(args.folder2):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), args.folder2)
                    print(f"  {rel_path}")
    else:
        combine_folders(args.folder1, args.folder2, args.merge)

if __name__ == "__main__":
    if len(os.sys.argv) == 1:
        print("Usage examples:")
        print("python Convert_dataset.py folder1 folder2 --merge  # Merge text files")
        print("python Convert_dataset.py folder1 folder2 --dry-run")
        print("\nFor smoke detection datasets:")
        print("python Convert_dataset.py dataset1/smoke_detection_annotations dataset2/smoke_detection_annotations")
    else:
        main()