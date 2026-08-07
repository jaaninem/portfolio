from PIL import Image
import os
import json
import argparse

# Configuration
PHOTO_DIR = "assets/photos"
THUMB_DIR = "assets/thumbs"
THUMB_WIDTH = 300  # pixels

def generate_thumbnails(photo_dir=PHOTO_DIR, thumb_dir=THUMB_DIR, thumb_width=THUMB_WIDTH):
    """
    Generate thumbnails for all images in photo directory
    that don't have existing thumbnails in thumb directory
    """
    # Create thumbnail directory if needed
    os.makedirs(thumb_dir, exist_ok=True)
    
    # Supported image formats
    img_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
    
    # Process all images in photo directory
    for root, _, files in os.walk(photo_dir):
        for filename in files:
            if filename.lower().endswith(img_exts):
                # Get relative path for directory structure
                rel_path = os.path.relpath(root, photo_dir)
                if rel_path == '.':
                    rel_path = ''
                
                # Create corresponding thumb directory
                thumb_subdir = os.path.join(thumb_dir, rel_path)
                os.makedirs(thumb_subdir, exist_ok=True)
                
                # Set paths
                photo_path = os.path.join(root, filename)
                thumb_path = os.path.join(thumb_subdir, filename)
                
                # Generate thumbnail if it doesn't exist
                if not os.path.exists(thumb_path):
                    try:
                        with Image.open(photo_path) as img:
                            # Calculate proportional height
                            wpercent = thumb_width / float(img.width)
                            hsize = int(float(img.height) * wpercent)
                            
                            # Create thumbnail
                            img.thumbnail(
                                (thumb_width, hsize),
                                Image.Resampling.LANCZOS
                            )
                            
                            # Save thumbnail
                            img.save(thumb_path)
                            print(f"Created thumbnail: {thumb_path}")
                    except Exception as e:
                        print(f"Error processing {photo_path}: {str(e)}")
                else:
                    print(f"Thumbnail exists: {thumb_path}")

def generate_manifest(photo_dir=PHOTO_DIR):
    """
    Generate a JSON manifest listing every image under the photo directory.
    The browser uses it to expand '*' glob patterns in gallery image paths.
    """
    # Supported image formats
    img_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp')

    files = []
    for root, _, filenames in os.walk(photo_dir):
        for filename in filenames:
            if filename.lower().endswith(img_exts):
                # Relative path, normalized to forward slashes for the browser
                rel_path = os.path.relpath(os.path.join(root, filename), photo_dir)
                files.append(rel_path.replace(os.sep, '/'))

    # Sort so glob expansion order is deterministic
    files.sort()

    manifest_path = os.path.join(photo_dir, 'manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(files, f, indent='\t')
    print(f"Created manifest: {manifest_path} ({len(files)} files)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate image thumbnails')
    parser.add_argument('--photo-dir', default=PHOTO_DIR, help='Photo directory path')
    parser.add_argument('--thumb-dir', default=THUMB_DIR, help='Thumbnail directory path')
    parser.add_argument('--width', type=int, default=THUMB_WIDTH, help='Thumbnail width in pixels')
    
    args = parser.parse_args()
    
    generate_thumbnails(
        photo_dir=args.photo_dir,
        thumb_dir=args.thumb_dir,
        thumb_width=args.width
    )

    generate_manifest(photo_dir=args.photo_dir)
