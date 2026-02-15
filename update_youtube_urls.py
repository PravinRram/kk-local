#!/usr/bin/env python3
"""
Script to update YouTube URLs in the database to proper embed format
This ensures all videos work correctly with the iframe embed approach
"""

from flask import Flask
from models import db, Song
import re


def create_app():
    """Create Flask app for database operations"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///karaoke.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def get_video_id(url):
    """Extract video ID from YouTube URL"""
    if not url:
        return None

    # Handle various YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^#&?\/\s]{11})',
        r'youtube\.com\/v\/([^#&?\/\s]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def convert_to_embed_url(url):
    """Convert any YouTube URL to proper embed format"""
    if not url:
        return url

    video_id = get_video_id(url)
    if video_id:
        # Return clean embed URL without tracking parameters
        return f"https://www.youtube.com/embed/{video_id}"

    return url


def update_youtube_urls():
    """Update all YouTube URLs in the database to embed format"""
    app = create_app()

    with app.app_context():
        songs = Song.query.all()
        updated_count = 0

        print(f"Found {len(songs)} songs in the database\n")

        for song in songs:
            if song.youtube_url:
                original_url = song.youtube_url
                new_url = convert_to_embed_url(original_url)

                if original_url != new_url:
                    print(f"Updating: {song.title} by {song.artist}")
                    print(f"  Old: {original_url}")
                    print(f"  New: {new_url}\n")

                    song.youtube_url = new_url
                    updated_count += 1
                else:
                    print(f"Already correct: {song.title} by {song.artist}")

        if updated_count > 0:
            db.session.commit()
            print(f"\n✓ Updated {updated_count} YouTube URLs to embed format")
        else:
            print("\n✓ All YouTube URLs are already in correct format")


if __name__ == '__main__':
    print("YouTube URL Update Script")
    print("=" * 50)
    print("This will convert all YouTube URLs to embed format\n")

    response = input("Continue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        update_youtube_urls()
    else:
        print("Update cancelled.")
