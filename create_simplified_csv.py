#!/usr/bin/env python3
import csv
import os

def create_simplified_csv(input_file, output_file):
    """
    Create a simplified CSV with only the id, author, and content columns.
    
    Args:
        input_file: Path to the input CSV file
        output_file: Path to the output CSV file
    """
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Read the input CSV and write the simplified CSV
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        
        # Create the output CSV file
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            fieldnames = ['id', 'autor', 'contenido']
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Process each row
            for row in reader:
                writer.writerow({
                    'id': row['post_id'],
                    'autor': row['author'],
                    'contenido': row['content']
                })
    
    print(f"Simplified CSV created successfully: {output_file}")

def main():
    # File paths
    input_file = "extracted_data/forum_posts.csv"
    output_file = "extracted_data/gitcoin_posts_simplified.csv"
    
    # Create the simplified CSV
    create_simplified_csv(input_file, output_file)

if __name__ == "__main__":
    main() 