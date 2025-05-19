import re
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics.pairwise import cosine_similarity
import logging
import os
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import potentially problematic libraries with fallbacks
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.warning("sentence_transformers not available. Some functionality will be limited.")
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import seaborn as sns
    import matplotlib.pyplot as plt
    VISUALIZATION_AVAILABLE = True
except ImportError:
    logger.warning("Visualization libraries not available. Visualization will be disabled.")
    VISUALIZATION_AVAILABLE = False

try:
    import pickle
    PICKLE_AVAILABLE = True
except ImportError:
    logger.warning("pickle not available. Caching will be disabled.")
    PICKLE_AVAILABLE = False

try:
    from scholarly import scholarly
    scholarly.set_retries(5)
    logging.getLogger('scholarly').setLevel(logging.WARNING)
    SCHOLARLY_AVAILABLE = True
except ImportError:
    logger.warning("scholarly not available. Google Scholar functionality will be limited.")
    SCHOLARLY_AVAILABLE = False

# Ensure cache directory exists
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def clean_author_name(name):
    """Remove Persian part of name and any special characters"""
    if not name or not isinstance(name, str):
        return "Unknown", "Unknown"
    
    try:
        parts = re.split(r'[-–()]', name)
        english_part = parts[0].strip()
        last_name = english_part.split()[-1]
        return english_part, last_name
    except Exception as e:
        logger.warning(f"Error cleaning name '{name}': {e}")
        return name, name.split()[-1] if name else "Unknown"

def get_author_data(scholar_id):
    """Fetch author data from Google Scholar"""
    try:
        # Try to load cached data
        cache_file = os.path.join(CACHE_DIR, f"cache_{scholar_id}.pkl")
        try:
            with open(cache_file, 'rb') as f:
                author = pickle.load(f)
            logger.info(f"Using cached data for {scholar_id}")
        except FileNotFoundError:
            author = scholarly.search_author_id(scholar_id)
            author = scholarly.fill(author, sections=['basics', 'publications'])
            with open(cache_file, 'wb') as f:
                pickle.dump(author, f)
        
        # Process publications
        publications = author.get('publications', [])
        pub_texts = []
        for pub in publications:
            title = pub.get('bib', {}).get('title', '')
            if title and len(title.split()) >= 3:  # Basic title length check
                pub_texts.append(title[:1000])  # Truncate long titles
        
        name = author.get('name', f"Unknown_{scholar_id}")
        return name, [], pub_texts
    
    except Exception as e:
        logger.error(f"Error processing {scholar_id}: {e}")
        return f"Error_{scholar_id}", [], []

def calculate_similarity(pub_vectors, course_vectors, method='sum'):
    """Calculate similarity scores with different aggregation methods"""
    similarity_matrix = cosine_similarity(pub_vectors, course_vectors)
    
    if method == 'sum':
        return np.sum(similarity_matrix, axis=0)
    elif method == 'max':
        return np.max(similarity_matrix, axis=0)
    elif method == 'mean':
        return np.mean(similarity_matrix, axis=0)
    else:
        raise ValueError("Invalid method. Choose from 'sum', 'mean', or 'max'")

def visualize_results(df, output_prefix="course_expertise", output_dir="results"):
    """Generate and save visualization of results"""
    os.makedirs(output_dir, exist_ok=True)
    
    plt.figure(figsize=(14, 10))
    sns.heatmap(df, annot=True, cmap='YlOrRd', fmt=".2f", 
                cbar_kws={'label': 'Expertise Score'})
    plt.title("Expertise Scores by Course", pad=20)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    # Generate unique filename
    unique_id = str(uuid.uuid4())[:8]
    output_path = os.path.join(output_dir, f"{output_prefix}_{unique_id}")
    
    # Save figures
    plt.savefig(f"{output_path}_heatmap.png", dpi=300)
    plt.savefig(f"{output_path}_heatmap.pdf")
    
    # Return paths for web display
    result_paths = {
        'png': f"{output_prefix}_{unique_id}_heatmap.png",
        'pdf': f"{output_prefix}_{unique_id}_heatmap.pdf",
        'csv': f"{output_prefix}_{unique_id}.csv"
    }
    
    plt.close()
    return result_paths

def run_analysis(courses, scholar_ids, method='sum', output_dir='results', progress_callback=None):
    """
    Run the analysis for the given courses and scholar IDs.
    
    Args:
        courses (list): List of course names
        scholar_ids (list): List of Google Scholar IDs
        method (str): Aggregation method ('sum', 'mean', or 'max')
        output_dir (str): Directory to save results
        progress_callback (callable): Function to call with progress updates
        
    Returns:
        tuple: (DataFrame of similarities, dict of result file paths)
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate a unique ID for this run
    run_id = str(uuid.uuid4())[:8]
    
    # Get embeddings for courses
    course_embeddings = get_embeddings(courses)
    
    # Get publications for each scholar
    all_publications = []
    
    for i, scholar_id in enumerate(scholar_ids):
        # Call progress callback if provided
        if progress_callback:
            progress_callback(i, scholar_id)
            
        publications = get_scholar_publications(scholar_id)
        all_publications.extend(publications)
    
    # Initialize model
    model = SentenceTransformer('allenai-specter')
    
    # Step 1: Fetch and process author data
    logger.info("Fetching author data...")
    results = Parallel(n_jobs=1)(delayed(get_author_data)(sid) for sid in scholar_ids)
    
    all_authors_data = {}
    last_names = {}
    
    for name, _, pub_texts in results:
        if not name.startswith("Error_"):
            clean_name, last_name = clean_author_name(name)
            all_authors_data[clean_name] = {'pub_texts': pub_texts}
            last_names[clean_name] = last_name
    
    # Step 2: Process courses
    logger.info(f"Encoding {len(courses)} courses...")
    course_vectors = model.encode(courses)
    
    # Step 3: Calculate expertise
    logger.info(f"Calculating expertise scores (method: {method})...")
    author_results = {}
    
    for name, data in all_authors_data.items():
        logger.info(f"Processing {name}...")
        if not data['pub_texts']:
            author_results[name] = np.zeros(len(courses))
            continue
            
        pub_vectors = model.encode(data['pub_texts'])
        author_results[name] = calculate_similarity(pub_vectors, course_vectors, method)
    
    # Create and sort results dataframe
    similarity_df = pd.DataFrame.from_dict(author_results,
                                        orient='index',
                                        columns=courses)
    similarity_df['Last_Name'] = similarity_df.index.map(last_names)
    similarity_df.sort_values('Last_Name', inplace=True)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate unique filename
    unique_id = str(uuid.uuid4())[:8]
    output_prefix = f"course_expertise_{method}_{unique_id}"
    
    # Save results
    output_csv = os.path.join(output_dir, f"{output_prefix}.csv")
    similarity_df.drop('Last_Name', axis=1).to_csv(output_csv)
    logger.info(f"Results saved to {output_csv}")
    
    # Visualize
    result_paths = visualize_results(similarity_df.drop('Last_Name', axis=1), 
                    f"course_expertise_{method}", output_dir)
    
    return similarity_df.drop('Last_Name', axis=1), result_paths

def main(method='sum'):
    """Main function with configurable similarity calculation method"""
    # Define course list (sorted alphabetically)
    COURSES = sorted([
        'Advanced Programming',
        'Algorithm Analysis',
        'Computer Vision',
        'Data Structure',
        'Database Systems',
        'Deep Learning',
        'Machine Learning',
        'Operating Systems',
        'Operations Research',
        'Programming Languages',
        'Software Engineering',
        'Theory of Computation'
    ])
    
    # Scholar IDs to process
    scholar_ids = [
        "HChhDEwAAAAJ",
        "eSspyHIAAAAJ",
        "onm7tt0AAAAJ",
        "ql5JirMAAAAJ",
        "x55q6n0AAAAJ"
    ]
    
    run_analysis(COURSES, scholar_ids, method)

if __name__ == "__main__":
    import argparse
    
    # Set up command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', type=str, default='sum',
                      choices=['sum', 'mean', 'max'],
                      help="Similarity calculation method (sum/mean/max)")
    args = parser.parse_args()
    
    main(method=args.method)