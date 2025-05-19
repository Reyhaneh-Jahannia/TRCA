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
    
    # Initialize model early to check if it loads correctly
    try:
        logger.info("Initializing sentence transformer model")
        model = SentenceTransformer('paraphrase-MiniLM-L3-v2') #paraphrase-multilingual-MiniLM-L12-v2
        # model = SentenceTransformer('paraphrase-MiniLM-L3-v2', 
        #                         device='cpu',
        #                         cache_folder='/tmp/models')
        logger.info("Model initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing model: {str(e)}")
        raise
    
    # Get embeddings for courses
    try:
        logger.info(f"Getting embeddings for {len(courses)} courses")
        course_embeddings = model.encode(courses, show_progress_bar=False)
        logger.info(f"Course embeddings shape: {course_embeddings.shape}")
    except Exception as e:
        logger.error(f"Error getting course embeddings: {str(e)}")
        raise
    
    # Process each scholar individually to better track progress
    all_authors_data = {}
    last_names = {}
    
    for i, scholar_id in enumerate(scholar_ids):
        try:
            # Call progress callback if provided
            if progress_callback:
                progress_callback(i, scholar_id)
            
            logger.info(f"Processing scholar {i+1}/{len(scholar_ids)}: {scholar_id}")
            
            # Get author data
            name, _, pub_texts = get_author_data(scholar_id)
            
            if not name.startswith("Error_"):
                clean_name, last_name = clean_author_name(name)
                all_authors_data[clean_name] = {'pub_texts': pub_texts}
                last_names[clean_name] = last_name
                logger.info(f"Successfully processed {clean_name} with {len(pub_texts)} publications")
            else:
                logger.warning(f"Error processing scholar {scholar_id}")
                
        except Exception as e:
            logger.error(f"Error processing scholar {scholar_id}: {str(e)}")
            # Continue with next scholar instead of failing completely
            continue
    
    # Calculate expertise scores
    logger.info(f"Calculating expertise scores (method: {method})...")
    author_results = {}
    
    for name, data in all_authors_data.items():
        logger.info(f"Processing {name}...")
        if not data['pub_texts']:
            author_results[name] = np.zeros(len(courses))
            continue
            
        try:
            # Process publications in smaller batches to reduce memory usage
            batch_size = 5
            pub_texts = data['pub_texts']
            num_batches = (len(pub_texts) + batch_size - 1) // batch_size
            
            # Initialize result array
            result = np.zeros(len(courses))
            
            for b in range(num_batches):
                start_idx = b * batch_size
                end_idx = min((b + 1) * batch_size, len(pub_texts))
                batch_texts = pub_texts[start_idx:end_idx]
                
                # Encode batch
                batch_vectors = model.encode(batch_texts, show_progress_bar=False)
                
                # Calculate similarity for batch
                batch_similarity = calculate_similarity(batch_vectors, course_embeddings, method)
                
                # Accumulate results based on method
                if method == 'sum':
                    result += batch_similarity
                elif method == 'max':
                    result = np.maximum(result, batch_similarity)
                # elif method == 'mean':
                #     # For mean, we'll accumulate and then divide by total count at the end
                #     result += batch_similarity * len(batch_texts)
            
            # # For mean method, divide by total count
            # if method == 'mean' and len(pub_texts) > 0:
            #     result /= len(pub_texts)
                
            author_results[name] = result
            
        except Exception as e:
            logger.error(f"Error calculating similarity for {name}: {str(e)}")
            author_results[name] = np.zeros(len(courses))
    
    # Create and sort results dataframe
    similarity_df = pd.DataFrame.from_dict(author_results,
                                        orient='index',
                                        columns=courses)
    similarity_df['Last_Name'] = similarity_df.index.map(last_names)
    similarity_df.sort_values('Last_Name', inplace=True)
    
    # Generate unique filename
    unique_id = str(uuid.uuid4())[:8]
    output_prefix = f"course_expertise_{method}_{unique_id}"
    
    # Save results
    output_csv = os.path.join(output_dir, f"{output_prefix}.csv")
    similarity_df.drop('Last_Name', axis=1).to_csv(output_csv)
    logger.info(f"Results saved to {output_csv}")
    
    # Visualize
    try:
        result_paths = visualize_results(similarity_df.drop('Last_Name', axis=1), 
                        f"course_expertise_{method}", output_dir)
        logger.info(f"Visualization saved: {result_paths}")
    except Exception as e:
        logger.error(f"Error creating visualization: {str(e)}")
        # Create a minimal result paths dict if visualization fails
        result_paths = {
            'csv': f"{output_prefix}.csv"
        }
    
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
    import os    
    # Set up command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', type=str, default='sum',
                      choices=['sum', 'mean', 'max'],
                      help="Similarity calculation method (sum/mean/max)")
    args = parser.parse_args()
    
    # os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
    # os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '600'  # 10 دقیقه

    # model = SentenceTransformer('paraphrase-MiniLM-L3-v2', 
    #                         device='cpu',
    #                         cache_folder='/tmp/models')

    main(method=args.method)