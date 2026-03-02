import nltk
import logging
import sys

def main():
    """
    Downloads the NLTK dependencies required for the server to run.
    This can be used during Docker image builds to pre-populate the NLTK data.
    """
    logging.basicConfig(level=logging.INFO)
    dependencies = ['punkt', 'punkt_tab']
    
    print("Starting NLTK dependency download...")
    for dep in dependencies:
        try:
            print(f"Downloading/verifying '{dep}'...")
            nltk.download(dep, quiet=True, raise_on_error=True)
            print(f"Successfully verified '{dep}'.")
        except Exception as e:
            print(f"Error downloading NLTK dependency '{dep}': {e}", file=sys.stderr)
            sys.exit(1)
            
    print("All NLTK dependencies verified successfully.")

if __name__ == "__main__":
    main()
