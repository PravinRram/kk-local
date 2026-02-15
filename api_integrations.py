"""
External API integrations for KampongKonek Karaoke
- LRCLIB: Free LRC format lyrics (perfect for karaoke)
- iTunes Search API: Free song search (no auth required)
- YouTube Data API: For finding karaoke videos
"""

import requests
from urllib.parse import quote
import re


class LyricsAPIError(Exception):
    """Exception raised for lyrics API errors"""
    pass


class SongSearchAPIError(Exception):
    """Exception raised for song search API errors"""
    pass


def fetch_lyrics_from_lrclib(title, artist, album=None, duration=None):
    """
    Fetch synced lyrics from LRCLIB.net

    Args:
        title: Song title
        artist: Artist name
        album: Album name (optional, helps with accuracy)
        duration: Song duration in seconds (optional, helps with accuracy)

    Returns:
        dict with 'lyrics' (LRC format), 'plain_lyrics', and metadata
        Returns None if not found
    """
    try:
        # LRCLIB API endpoint for searching
        base_url = "https://lrclib.net/api/search"

        # Build query parameters
        params = {
            'track_name': title,
            'artist_name': artist
        }

        if album:
            params['album_name'] = album

        if duration:
            params['duration'] = int(duration)

        # Make request
        response = requests.get(base_url, params=params, timeout=5)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        results = response.json()

        if not results or len(results) == 0:
            return None

        # Get the first (best) match
        result = results[0]

        # Check if synced lyrics are available
        synced_lyrics = result.get('syncedLyrics')
        plain_lyrics = result.get('plainLyrics')

        if not synced_lyrics and not plain_lyrics:
            return None

        return {
            'lyrics': synced_lyrics if synced_lyrics else plain_lyrics,
            'plain_lyrics': plain_lyrics,
            'instrumental': result.get('instrumental', False),
            'duration': result.get('duration'),
            'album': result.get('albumName'),
            'source': 'lrclib'
        }

    except requests.exceptions.Timeout:
        raise LyricsAPIError("Lyrics API request timed out")
    except requests.exceptions.RequestException as e:
        raise LyricsAPIError(f"Error fetching lyrics: {str(e)}")
    except (KeyError, ValueError, TypeError) as e:
        raise LyricsAPIError(f"Error parsing lyrics response: {str(e)}")


def extract_youtube_id(url):
    """
    Extract YouTube video ID from various URL formats

    Args:
        url: YouTube URL (youtube.com/watch?v=ID or youtu.be/ID)

    Returns:
        Video ID string or None
    """
    if not url:
        return None

    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def search_songs_itunes(query, limit=20):
    """
    Search for songs using iTunes Search API
    Free API, no authentication required

    Args:
        query: Search query (song title, artist, etc.)
        limit: Maximum number of results (default 20)

    Returns:
        List of song dictionaries with title, artist, album, duration, artwork, etc.
    """
    try:
        base_url = "https://itunes.apple.com/search"

        params = {
            'term': query,
            'media': 'music',
            'entity': 'song',
            'limit': limit,
            'explicit': 'No'  # Filter explicit content for family-friendly karaoke
        }

        response = requests.get(base_url, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()
        results = data.get('results', [])

        songs = []
        for item in results:
            # Convert milliseconds to seconds
            duration_ms = item.get('trackTimeMillis', 0)
            duration = int(duration_ms / 1000) if duration_ms else 180

            songs.append({
                'title': item.get('trackName', 'Unknown'),
                'artist': item.get('artistName', 'Unknown Artist'),
                'album': item.get('collectionName', ''),
                'genre': item.get('primaryGenreName', 'Pop'),
                'duration': duration,
                'artwork_url': item.get('artworkUrl100', ''),
                'preview_url': item.get('previewUrl', ''),
                'release_date': item.get('releaseDate', ''),
                'itunes_id': item.get('trackId'),
                'source': 'itunes'
            })

        return songs

    except requests.exceptions.Timeout:
        raise SongSearchAPIError("Song search API request timed out")
    except requests.exceptions.RequestException as e:
        raise SongSearchAPIError(f"Error searching songs: {str(e)}")
    except (KeyError, ValueError, TypeError) as e:
        raise SongSearchAPIError(f"Error parsing search results: {str(e)}")


def search_youtube_karaoke(song_title, artist, max_results=5):
    """
    Search for karaoke versions of songs on YouTube

    Note: This is a simplified version that constructs search URLs.
    For production, you should use the YouTube Data API v3 with an API key.

    Args:
        song_title: Song title
        artist: Artist name
        max_results: Maximum number of results

    Returns:
        List of suggested search URLs (or results if API key is available)
    """
    # Construct karaoke search query
    query = f"{song_title} {artist} karaoke"
    encoded_query = quote(query)

    # Return search URL for now
    # In production, integrate with YouTube Data API v3
    return {
        'search_url': f"https://www.youtube.com/results?search_query={encoded_query}",
        'query': query,
        'note': 'Use YouTube Data API v3 for automated results'
    }


def get_song_difficulty(duration):
    """
    Estimate song difficulty based on duration
    This is a simple heuristic - can be enhanced with more factors

    Args:
        duration: Song duration in seconds

    Returns:
        'easy', 'medium', or 'hard'
    """
    if duration < 150:  # Less than 2.5 minutes
        return 'easy'
    elif duration < 270:  # Less than 4.5 minutes
        return 'medium'
    else:
        return 'hard'


def validate_youtube_url(url):
    """
    Validate that a URL is a valid YouTube URL

    Args:
        url: URL string to validate

    Returns:
        Boolean indicating if URL is valid YouTube URL
    """
    if not url:
        return False

    video_id = extract_youtube_id(url)
    return video_id is not None
