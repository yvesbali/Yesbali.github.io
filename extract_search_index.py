#!/usr/bin/env python3
"""
Extract video data from LCDMH hub pages and generate search-index.json
"""
import json
import re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse

BASE_PATH = Path(__file__).parent

# Hub pages to process with their relative URLs
HUB_PAGES = [
    ("roadtrips/road-trip-moto-france.html", "/roadtrips/road-trip-moto-france.html"),
    ("roadtrips/alpes-dans-tous-les-sens.html", "/roadtrips/alpes-dans-tous-les-sens.html"),
    ("roadtrips/road-trip-espagne-solo.html", "/roadtrips/road-trip-espagne-solo.html"),
    ("roadtrips/securite-routiere-moto.html", "/roadtrips/securite-routiere-moto.html"),
    ("roadtrips/maquette_capnord_complete_v2.html", "/roadtrips/maquette_capnord_complete_v2.html"),
    ("europe-asie-moto.html", "/europe-asie-moto.html"),
    ("roadtrips/road-trip-turquie-cappadoce.html", "/roadtrips/road-trip-turquie-cappadoce.html"),
    ("roadtrips/road-trip-cap-nord-2025.html", "/roadtrips/road-trip-cap-nord-2025.html"),
]

class VideoExtractor(HTMLParser):
    """Extract video cards from HTML"""

    def __init__(self):
        super().__init__()
        self.videos = []
        self.current_video = None
        self.in_card = False
        self.in_title = False
        self.in_description = False
        self.in_tags = False
        self.in_situation = False
        self.tag_text = ""
        self.char_buffer = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Start of video card
        if tag == "article" and "video-card" in attrs_dict.get("class", ""):
            self.in_card = True
            self.current_video = {
                "videoId": None,
                "title": "",
                "description": "",
                "tags": [],
                "zone": "",
                "thumbnail": "",
                "episode": "",
                "link": ""
            }

        # Get YouTube video ID from link
        if self.in_card and tag == "a" and "href" in attrs_dict:
            href = attrs_dict["href"]
            if "youtube.com/watch" in href:
                match = re.search(r"v=([a-zA-Z0-9_-]+)", href)
                if match:
                    self.current_video["videoId"] = match.group(1)
                    self.current_video["link"] = href

        # Get thumbnail
        if self.in_card and tag == "img" and "src" in attrs_dict:
            src = attrs_dict["src"]
            if "ytimg.com" in src:
                self.current_video["thumbnail"] = src

        # Situation (geographic info)
        if self.in_card and tag == "div" and "card-situation" in attrs_dict.get("class", ""):
            self.in_situation = True

        # Title
        if self.in_card and tag == "h3":
            self.in_title = True
            self.char_buffer = []

        # Description
        if self.in_card and tag == "p" and "card-desc" in attrs_dict.get("class", ""):
            self.in_description = True
            self.char_buffer = []

        # Tags
        if self.in_card and tag == "div" and "card-tags" in attrs_dict.get("class", ""):
            self.in_tags = True

        # Episode badge
        if self.in_card and tag == "div" and "ep-badge" in attrs_dict.get("class", ""):
            self.char_buffer = []
            self.in_title = True  # Reuse to capture badge text

    def handle_endtag(self, tag):
        # End of card
        if tag == "article" and self.in_card:
            if self.current_video["videoId"]:
                self.videos.append(self.current_video)
            self.in_card = False
            self.current_video = None

        # Situation
        if tag == "div" and self.in_situation:
            self.in_situation = False

        # Title
        if tag == "h3" and self.in_title:
            self.in_title = False
            text = "".join(self.char_buffer).strip()
            if text and not self.current_video["title"]:
                self.current_video["title"] = text
            self.char_buffer = []

        # Description
        if tag == "p" and self.in_description:
            self.in_description = False
            text = "".join(self.char_buffer).strip()
            self.current_video["description"] = text
            self.char_buffer = []

        # Tags
        if tag == "div" and self.in_tags:
            self.in_tags = False

    def handle_data(self, data):
        if self.in_situation:
            # Extract zone from situation text
            if "g" in data or "Situation" in data:
                if not self.current_video["zone"]:
                    # Look for location markers
                    if "Étape" in data or "Étapes" in data:
                        text = data.strip()
                        if text and text not in ["Situation", "Étape"]:
                            self.current_video["zone"] = text

        if self.in_title:
            self.char_buffer.append(data.strip())

        if self.in_description:
            self.char_buffer.append(data)

        if self.in_tags:
            text = data.strip()
            if text and text not in ["", " "]:
                # Look for tags starting with emojis or keywords
                if any(c in text for c in ["🇫🇷", "🇪🇸", "🇹🇷", "🌍", "📎", "EP", "Prépa", "Film"]):
                    if text not in self.current_video["tags"]:
                        self.current_video["tags"].append(text)

def extract_videos_from_file(file_path, page_url):
    """Extract all videos from an HTML file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        parser = VideoExtractor()
        parser.feed(content)

        # Add page URL to each video
        for video in parser.videos:
            video["pageUrl"] = page_url

        return parser.videos
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return []

def main():
    all_videos = []

    print("Extracting videos from hub pages...")

    for file_path, page_url in HUB_PAGES:
        full_path = BASE_PATH / file_path
        if full_path.exists():
            print(f"  Processing: {file_path}")
            videos = extract_videos_from_file(full_path, page_url)
            all_videos.extend(videos)
            print(f"    Found {len(videos)} videos")
        else:
            print(f"  WARNING: File not found: {file_path}")

    # Create data directory if it doesn't exist
    data_dir = BASE_PATH / "data"
    data_dir.mkdir(exist_ok=True)

    # Write search index
    output_file = data_dir / "search-index.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_videos, f, ensure_ascii=False, indent=2)

    print(f"\nTotal videos extracted: {len(all_videos)}")
    print(f"Search index written to: {output_file}")

    # Print summary
    print("\nSummary by page:")
    pages_count = {}
    for video in all_videos:
        page = video.get("pageUrl", "unknown")
        pages_count[page] = pages_count.get(page, 0) + 1

    for page, count in sorted(pages_count.items()):
        print(f"  {page}: {count} videos")

if __name__ == "__main__":
    main()
