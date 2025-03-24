#!/usr/bin/env python3
import os
import re
import json
import glob
import csv
from typing import Dict, List, Tuple, Optional
import argparse
from dataclasses import dataclass

@dataclass
class ForumPost:
    post_id: str
    author: str
    content: str
    timestamp: str
    url: str
    is_root_post: bool
    topic_title: Optional[str] = None
    topic_url: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "post_id": self.post_id,
            "author": self.author,
            "content": self.content,
            "timestamp": self.timestamp,
            "url": self.url,
            "is_root_post": self.is_root_post,
            "topic_title": self.topic_title,
            "topic_url": self.topic_url
        }
        
    def to_list(self) -> List:
        """Convert the post to a list for CSV output."""
        return [
            self.post_id,
            self.author,
            self.content,
            self.timestamp,
            self.url,
            str(self.is_root_post),
            self.topic_title or "",
            self.topic_url or ""
        ]

def extract_data_from_file(file_path: str, debug: bool = False) -> List[ForumPost]:
    """Extract post data from a Gitcoin forum RSS file."""
    
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    # Special case for Monthly Update files that have a specific pattern
    file_name = os.path.basename(file_path)
    if "Monthly_Update" in file_name or "monthly_update" in file_name:
        if debug:
            print("Detected Monthly Update file, using special parsing")
        
        # Try to extract title and URL from the beginning of file
        lines = content.strip().split('\n')
        title = None
        url = None
        
        for i, line in enumerate(lines[:10]):  # Look in first 10 lines
            line = line.strip()
            if line and not title:
                title = line
                if debug:
                    print(f"Found title: {title}")
            elif line.startswith('http') and not url:
                url = line
                if debug:
                    print(f"Found URL: {url}")
                break
        
        # Extract timestamp
        timestamp_pattern = re.compile(r'([A-Za-z]{3}, \d+ [A-Za-z]+ \d{4} \d+:\d+:\d+ \+\d{4})')
        timestamp_match = timestamp_pattern.search(content)
        timestamp = timestamp_match.group(1) if timestamp_match else ""
        
        # Extract author - often a standard format for monthly updates
        author = "Gitcoin Team"
        author_pattern = re.search(r'(MathildaDV|Kevin Owocki|kbw|owocki)', content)
        if author_pattern:
            author = author_pattern.group(1)
        
        # Extract content
        # First, try to extract HTML content
        html_content = ""
        p_tags_pattern = re.compile(r'<p>(.*?)<\/p>', re.DOTALL)
        p_tags_matches = p_tags_pattern.findall(content)
        
        if p_tags_matches:
            html_content = ' '.join(p_tags_matches)
            
        # If we found HTML content, clean it
        if html_content:
            # Remove HTML tags
            clean_content = re.sub(r'<.*?>', ' ', html_content)
            # Replace multiple spaces with single space
            clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        else:
            # If no HTML content, extract text content after URL until timestamp
            if url and timestamp:
                url_pos = content.find(url)
                timestamp_pos = content.find(timestamp)
                
                if url_pos > -1 and timestamp_pos > url_pos:
                    text_content = content[url_pos + len(url):timestamp_pos].strip()
                    clean_content = re.sub(r'\s+', ' ', text_content).strip()
                else:
                    # Just take everything after the URL
                    clean_content = content[url_pos + len(url):].strip()
                    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
            else:
                # Fallback: take all content
                clean_content = re.sub(r'\s+', ' ', content).strip()
        
        # Extract topic ID from URL
        topic_id = ""
        if url:
            topic_id_match = re.search(r'/t/[^/]+/(\d+)', url)
            if topic_id_match:
                topic_id = topic_id_match.group(1)
        
        # Create post
        if title and clean_content:
            post = ForumPost(
                post_id=f"{topic_id}-1" if topic_id else "unknown",
                author=author,
                content=clean_content,
                timestamp=timestamp,
                url=url or "",
                is_root_post=True,
                topic_title=title,
                topic_url=url
            )
            
            if debug:
                print(f"Created Monthly Update post: {post.post_id} by {post.author}")
                print(f"Content length: {len(post.content)} characters")
            
            return [post]
        else:
            if debug:
                print("Could not create Monthly Update post: missing title or content")
    
    # General extraction for any forum post file
    # First, try to extract the title and URL
    lines = content.strip().split('\n')
    title = None
    url = None
    
    # Try to find the title and URL at the beginning
    for i, line in enumerate(lines[:10]):  # Look in first 10 lines
        line = line.strip()
        if line and not title and not line.startswith('http'):
            title = line
            if debug:
                print(f"Found title: {title}")
        elif line.startswith('http') and not url:
            url = line
            if debug:
                print(f"Found URL: {url}")
            break
    
    # Now try to extract post matches using the regular pattern
    post_pattern = re.compile(
        r'([^\n]+?)\n\s+<p>.*?<\/p>\s+<p><a href="(https://gov\.gitcoin\.co/t/[^"]+)">Read full topic<\/a><\/p>\s+'
        r'(https://gov\.gitcoin\.co/t/[^/]+/\d+(?:/\d+)?)\s+([^\\n]+?)\s+'
        r'(gov\.gitcoin\.co-post-(\d+)-(\d+))\s+([^\n]+)',
        re.DOTALL
    )
    
    # Extract post content
    content_pattern = re.compile(r'<p>(.*?)<\/p>\s+<p><a href="', re.DOTALL)
    
    posts = []
    
    # Find all post matches in the file
    matches = list(post_pattern.finditer(content))
    if debug:
        print(f"Found {len(matches)} post matches using regular pattern.")
    
    # Process each post match
    for i, match in enumerate(matches):
        author = match.group(1).strip()
        read_full_topic_url = match.group(2)
        post_url = match.group(3)
        timestamp = match.group(4).strip()
        post_id_full = match.group(5)
        topic_id = match.group(6)
        post_number = match.group(7)
        post_title = match.group(8).strip()
        
        # Extract post ID
        post_id = f"{topic_id}-{post_number}"
        
        # Extract post content
        # Get the text between the current match and the next match or end of file
        if i < len(matches) - 1:
            post_text = content[match.start():matches[i+1].start()]
        else:
            post_text = content[match.start():]
        
        # Extract content using regex
        content_match = content_pattern.search(post_text)
        if content_match:
            post_content = content_match.group(1)
        else:
            # If regex fails, try to extract content between <p> tags
            p_tags_pattern = re.compile(r'<p>(.*?)<\/p>', re.DOTALL)
            p_tags_matches = p_tags_pattern.findall(post_text)
            post_content = ' '.join(p_tags_matches) if p_tags_matches else ""
        
        # Determine if this is a root post (first post in a topic)
        is_root_post = post_number == "1"
        
        # Clean the content (remove HTML tags)
        post_content = re.sub(r'<.*?>', ' ', post_content)
        post_content = re.sub(r'\s+', ' ', post_content).strip()
        
        post = ForumPost(
            post_id=post_id,
            author=author,
            content=post_content,
            timestamp=timestamp,
            url=post_url,
            is_root_post=is_root_post,
            topic_title=title,
            topic_url=url
        )
        
        posts.append(post)
    
    # If no posts found yet and we have a title/URL, try to extract the main post
    if not posts and title and url:
        if debug:
            print(f"No post matches found. Attempting to extract main post content for: {title}")
        
        # Extract timestamp
        timestamp_pattern = re.compile(r'([A-Za-z]{3}, \d+ [A-Za-z]+ \d{4} \d+:\d+:\d+ \+\d{4})')
        timestamp_match = timestamp_pattern.search(content)
        timestamp = timestamp_match.group(1) if timestamp_match else ""
        
        # Try to extract the post's main content (everything after URL until timestamp or end)
        url_pos = content.find(url)
        if url_pos > -1:
            if timestamp:
                timestamp_pos = content.find(timestamp)
                if timestamp_pos > url_pos:
                    main_content = content[url_pos + len(url):timestamp_pos].strip()
                else:
                    main_content = content[url_pos + len(url):].strip()
            else:
                main_content = content[url_pos + len(url):].strip()
            
            # Try to find author after URL
            author = "Unknown"
            author_lines = main_content.split('\n', 3)
            for line in author_lines[:2]:
                if line.strip() and not line.startswith('http') and not line.startswith('<'):
                    author = line.strip()
                    break
            
            # Extract topic ID from URL
            topic_id = ""
            topic_id_match = re.search(r'/t/[^/]+/(\d+)', url)
            if topic_id_match:
                topic_id = topic_id_match.group(1)
            
            # Clean up and extract post content
            # First see if there are HTML <p> tags
            p_tags_pattern = re.compile(r'<p>(.*?)<\/p>', re.DOTALL)
            p_tags_matches = p_tags_pattern.findall(main_content)
            
            if p_tags_matches:
                # Join all the paragraph content
                post_content = ' '.join(p_tags_matches)
                # Clean HTML tags
                post_content = re.sub(r'<.*?>', ' ', post_content)
                post_content = re.sub(r'\s+', ' ', post_content).strip()
            else:
                # No HTML tags, just use the main content
                post_content = re.sub(r'\s+', ' ', main_content).strip()
            
            # Create and add the post
            post = ForumPost(
                post_id=f"{topic_id}-1" if topic_id else "unknown",
                author=author,
                content=post_content,
                timestamp=timestamp,
                url=url,
                is_root_post=True,
                topic_title=title,
                topic_url=url
            )
            
            posts.append(post)
            if debug:
                print(f"Extracted main post with id {post.post_id} by {post.author}")
                print(f"Content length: {len(post.content)} characters")
    
    # If we still couldn't extract any posts with previous methods
    if not posts and title:
        # Check if this is a digest or update file
        is_digest = any(keyword in title.lower() for keyword in ["digest", "update", "roundup", "monthly"])
        
        if debug:
            print(f"No posts found yet. Is this a digest file? {is_digest}")
            
            # Print more detailed info about the file structure
            print(f"File structure overview:")
            lines = content.split('\n')
            if len(lines) > 10:
                print(f"First 10 lines: {lines[:10]}")
            else:
                print(f"All lines ({len(lines)}): {lines}")
                
            # Check if this file has HTML content
            has_html = "<p>" in content
            print(f"Has HTML content: {has_html}")
            
            # Check for standard Gitcoin post patterns
            post_id_pattern = re.compile(r'gov\.gitcoin\.co-post-(\d+)-(\d+)')
            post_ids = post_id_pattern.findall(content)
            print(f"Found {len(post_ids)} post IDs in content")
            
            # Extract specific content for monthly update posts
            if "Monthly Update" in title:
                print("This is a Monthly Update post. Looking for specific content.")
                
                # Look for author section
                author_section = re.search(r'\n([^\n]+?)\n\s+<p>', content)
                if author_section:
                    print(f"Found author section: {author_section.group(1)}")
                else:
                    print("No author section found")
                
                # Find all paragraphs
                paragraphs = re.findall(r'<p>(.*?)<\/p>', content)
                print(f"Found {len(paragraphs)} paragraphs")
                if paragraphs:
                    print(f"First paragraph: {paragraphs[0][:100]}...")
        
        if is_digest:
            # For digest files, extract content directly after the URL
            if url:
                # Extract the content section
                url_index = content.find(url)
                if url_index > -1:
                    content_start = url_index + len(url)
                    main_content = content[content_start:].strip()
                    
                    # Extract timestamp if available
                    timestamp_pattern = re.compile(r'([A-Za-z]{3}, \d+ [A-Za-z]+ \d{4} \d+:\d+:\d+ \+\d{4})')
                    timestamp_match = timestamp_pattern.search(main_content)
                    timestamp = timestamp_match.group(1) if timestamp_match else ""
                    
                    # Extract the first lines for author
                    first_lines = main_content.split('\n', 3)
                    author = "Gitcoin Team"
                    for line in first_lines[:2]:
                        if line.strip() and not line.startswith('http') and not timestamp_pattern.search(line):
                            author = line.strip()
                            break
                    
                    # Clean the content
                    # Remove HTML tags from content
                    clean_content = re.sub(r'<.*?>', ' ', main_content)
                    # Replace multiple spaces with a single space
                    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
                    
                    # Extract topic ID from URL
                    topic_id = ""
                    topic_id_match = re.search(r'/t/[^/]+/(\d+)', url)
                    if topic_id_match:
                        topic_id = topic_id_match.group(1)
                    
                    # Create and add the post
                    post = ForumPost(
                        post_id=f"{topic_id}-1" if topic_id else "unknown",
                        author=author,
                        content=clean_content,
                        timestamp=timestamp,
                        url=url,
                        is_root_post=True,
                        topic_title=title,
                        topic_url=url
                    )
                    
                    posts.append(post)
                    if debug:
                        print(f"Extracted digest post with id {post.post_id} by {post.author}")
                else:
                    if debug:
                        print(f"Could not find URL {url} in content")
        else:
            # Try to find the root post with a different pattern
            root_post_pattern = re.compile(
                r'(.*?)\n\s+<p>(.*?)(?:<\/p>|$)',
                re.DOTALL
            )
            
            # Look for timestamp pattern
            timestamp_pattern = re.compile(r'([A-Za-z]{3}, \d+ [A-Za-z]+ \d{4} \d+:\d+:\d+ \+\d{4})')
            
            # Try to find topic ID from URL
            topic_id = ""
            if url:
                topic_id_match = re.search(r'/t/[^/]+/(\d+)', url)
                if topic_id_match:
                    topic_id = topic_id_match.group(1)
            
            # Try finding the root post
            root_match = root_post_pattern.search(content)
            if debug:
                print(f"Looking for root post. Found match? {root_match is not None}")
            
            if root_match:
                author = root_match.group(1).strip()
                raw_content = root_match.group(2)
                
                # Clean up the content
                post_content = re.sub(r'<.*?>', ' ', raw_content)
                post_content = re.sub(r'\s+', ' ', post_content).strip()
                
                # Look for timestamp
                timestamp_match = timestamp_pattern.search(content)
                timestamp = timestamp_match.group(1) if timestamp_match else ""
                
                post = ForumPost(
                    post_id=f"{topic_id}-1" if topic_id else "unknown",
                    author=author,
                    content=post_content,
                    timestamp=timestamp,
                    url=url or "",
                    is_root_post=True,
                    topic_title=title,
                    topic_url=url
                )
                
                posts.append(post)
                if debug:
                    print(f"Extracted root post with id {post.post_id} by {post.author}")
                
            # Last resort: look for the main content block
            elif "<p>" in content and title:
                if debug:
                    print("Trying to extract post from main content block")
                
                # Extract the main content after the title
                content_sections = content.split("\n\n", 2)
                if len(content_sections) >= 3:
                    main_content = content_sections[2]
                    
                    # Try to get author
                    author_match = re.search(r'^\s*(.*?)\s*$', content_sections[1], re.MULTILINE)
                    author = author_match.group(1) if author_match else "Unknown"
                    
                    # Try to extract content from p tags
                    p_tags_pattern = re.compile(r'<p>(.*?)<\/p>', re.DOTALL)
                    p_tags_matches = p_tags_pattern.findall(main_content)
                    
                    if p_tags_matches:
                        raw_content = ' '.join(p_tags_matches)
                        post_content = re.sub(r'<.*?>', ' ', raw_content)
                        post_content = re.sub(r'\s+', ' ', post_content).strip()
                        
                        # Look for timestamp
                        timestamp_match = timestamp_pattern.search(content)
                        timestamp = timestamp_match.group(1) if timestamp_match else ""
                        
                        post = ForumPost(
                            post_id=f"{topic_id}-1" if topic_id else "unknown",
                            author=author,
                            content=post_content,
                            timestamp=timestamp,
                            url=url or "",
                            is_root_post=True,
                            topic_title=title,
                            topic_url=url
                        )
                        
                        posts.append(post)
                        if debug:
                            print(f"Extracted post from content block with id {post.post_id} by {post.author}")
                    elif debug:
                        print("No p tags found in main content block")
                elif debug:
                    print(f"Not enough content sections in file (found {len(content_sections)})")
            elif debug:
                print("No HTML <p> tags in content or missing topic title")
    
    if debug and not posts and title:
        print(f"Warning: Could not extract any posts from {os.path.basename(file_path)}")
    
    return posts

def save_to_json(posts: List[ForumPost], output_file: str) -> None:
    """Save posts to a JSON file."""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Convert to dictionaries for JSON serialization
    all_posts_dict = [post.to_dict() for post in posts]
    
    # Save to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_posts_dict, f, ensure_ascii=False, indent=2)

def save_to_csv(posts: List[ForumPost], output_file: str) -> None:
    """Save posts to a CSV file."""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Define headers
    headers = ["post_id", "author", "content", "timestamp", "url", "is_root_post", "topic_title", "topic_url"]
    
    # Write to CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for post in posts:
            writer.writerow(post.to_list())

def process_directory(directory_path: str, output_file: str, format_type: str = "json", 
                      limit: Optional[int] = None, debug: bool = False) -> None:
    """Process all RSS files in the given directory and save results to file."""
    
    all_posts = []
    processed_count = 0
    
    # Get all .txt files in the directory
    file_paths = glob.glob(os.path.join(directory_path, "*.txt"))
    
    # Sort files to get consistent results
    file_paths.sort()
    
    # Limit the number of files to process if specified
    if limit:
        file_paths = file_paths[:limit]
    
    print(f"Processing {len(file_paths)} files...")
    
    for file_path in file_paths:
        try:
            file_posts = extract_data_from_file(file_path, debug)
            all_posts.extend(file_posts)
            processed_count += 1
            print(f"Processed {processed_count}/{len(file_paths)}: {os.path.basename(file_path)} - Found {len(file_posts)} posts")
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    # Save to file in the chosen format
    if format_type.lower() == "csv":
        save_to_csv(all_posts, output_file)
    else:  # Default to JSON
        save_to_json(all_posts, output_file)
    
    print(f"Extracted {len(all_posts)} posts from {processed_count} files")
    print(f"Results saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Extract data from Gitcoin forum RSS files")
    parser.add_argument("--directory", "-d", default="rss_files", help="Directory containing RSS files")
    parser.add_argument("--output", "-o", help="Output file (default: extracted_data/forum_posts.[json|csv])")
    parser.add_argument("--format", "-fmt", choices=["json", "csv"], default="json", 
                        help="Output format (json or csv)")
    parser.add_argument("--limit", "-l", type=int, help="Limit the number of files to process")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode for more verbose output")
    parser.add_argument("--file", "-f", help="Process a single file instead of a directory")
    args = parser.parse_args()
    
    # Set default output file based on format if not provided
    if not args.output:
        if args.format.lower() == "csv":
            args.output = "extracted_data/forum_posts.csv"
        else:
            args.output = "extracted_data/forum_posts.json"
    
    if args.file:
        # Process a single file
        try:
            file_posts = extract_data_from_file(args.file, args.debug)
            
            # Save to file in the chosen format
            if args.format.lower() == "csv":
                save_to_csv(file_posts, args.output)
            else:  # Default to JSON
                save_to_json(file_posts, args.output)
            
            print(f"Extracted {len(file_posts)} posts from {args.file}")
            print(f"Results saved to {args.output}")
        except Exception as e:
            print(f"Error processing {args.file}: {str(e)}")
    else:
        # Process all files in the directory
        process_directory(args.directory, args.output, args.format, args.limit, args.debug)

if __name__ == "__main__":
    main() 