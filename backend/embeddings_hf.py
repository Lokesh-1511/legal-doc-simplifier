"""
Lightweight Hugging Face Inference API embeddings wrapper.

Uses Hugging Face's hosted embeddings API to avoid local model dependencies.
No PyTorch, transformers, or CUDA required.
"""

import os
from typing import List
import requests
import numpy as np


def get_hf_embeddings(texts: List[str]) -> np.ndarray:
    """
    Call Hugging Face Inference API and return embeddings as numpy array.
    
    Uses the all-MiniLM-L6-v2 model for semantic embeddings.
    
    Args:
        texts: List of text strings to embed.
    
    Returns:
        Numpy array of shape (len(texts), 384).
    
    Raises:
        ValueError: If HF_API_TOKEN is not set.
        requests.RequestException: If API call fails.
    """
    api_token = os.getenv("HF_API_TOKEN")
    if not api_token:
        raise ValueError(
            "HF_API_TOKEN environment variable not set. "
            "Get a free token at https://huggingface.co/settings/tokens"
        )
    
    if not texts:
        return np.array([])
    
    # Hugging Face Inference API endpoint for all-MiniLM-L6-v2
    url = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": texts,
    }
    
    print(f"📤 Embedding {len(texts)} text(s) via Hugging Face API...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        embeddings = response.json()
        
        # HF returns list of embeddings (each is a list of floats)
        embeddings_array = np.array(embeddings, dtype=np.float32)
        print(f"✅ Got embeddings with shape {embeddings_array.shape}")
        
        return embeddings_array
    
    except requests.exceptions.Timeout:
        print("❌ Embedding request timed out (30s)")
        raise
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        raise
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error: {response.status_code} - {response.text}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error during embedding: {e}")
        raise
