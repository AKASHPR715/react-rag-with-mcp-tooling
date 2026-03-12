# ============================================================
# 📄 Unified Tax Form Extraction Pipeline (VS Code-ready)
# ============================================================

import os
from pathlib import Path
import json
import uuid
from datetime import datetime
from typing import List, Optional, Type
from pydantic import BaseModel
from llama_cloud_services import LlamaExtract
from llama_cloud.types import ExtractConfig
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from pymongo import MongoClient

# Import DB Models and Connection
from app.db.models import (
    Form16PartA, Form16PartB, AIS, User,
    Form16PartA_Schema, Form16PartB_Schema, AIS_Schema
)
from app.db.connection import get_sync_db

# 🛠️ PATCH: Fix LlamaCloud API/Model Discrepancies
from app.utils.llama_patch import apply_llama_cloud_patch
apply_llama_cloud_patch()

# ============================================================
# Logging Configuration for form_extraction.py
# ============================================================
def setup_extraction_logger():
    """Set up logging for form extraction to separate log file."""
    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "form_extraction.log"
    
    logger = logging.getLogger("form_extraction")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        # File handler with rotation
        fh = RotatingFileHandler(
            log_file, 
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=2,
            encoding="utf-8"
        )
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(fh)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(levelname)s: %(message)s"
        ))
        logger.addHandler(ch)
    
    return logger

extraction_logger = setup_extraction_logger()

# 🔐 Load environment variables and initialize extractors
# ------------------------------------------------------------
load_dotenv()  # Loads .env file

# LlamaExtract (Sole Extraction Method)
LLAMA_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

if not LLAMA_API_KEY:
    extraction_logger.warning("LLAMA_CLOUD_API_KEY not found. Extraction will fail.")

extraction_logger.info("Using LlamaExtract (default method)")
# Initialize extractor
extractor = LlamaExtract(
    api_key=LLAMA_API_KEY,
    max_timeout=120000,
    httpx_timeout=120.0
)

# ============================================================
# 🛡️ Database Helper Functions
# ============================================================

def get_or_create_default_user(db_client) -> str:
    """
    Get a default user for standalone script execution context.
    If no user exists, create a Test User.
    """
    users_collection = db_client["users"]
    
    # Try to find an existing user - specifically "Test User" if possible
    user = users_collection.find_one({"full_name": "Test User"})
    if not user:
        # If no Test User, try ANY user
        user = users_collection.find_one({})
    
    if user:
        extraction_logger.info(f"Using existing user: {user.get('full_name')} ({user['_id']})")
        return user["_id"]
    
    # Create new Test User if database is empty
    new_user = User(
        email="test_user@example.com",
        full_name="Test User",
        pan_number="ABCDE1234F"
    )
    # Convert to dict for mongo insertion (excluding _id to let mongo or model handle it)
    user_dict = new_user.model_dump(by_alias=True, exclude={"id"})
    result = users_collection.insert_one(user_dict)
    extraction_logger.info(f"Created new Test User with ID: {result.inserted_id}")
    return result.inserted_id

def save_extraction_to_db(data: dict, schema_class: Type[BaseModel], user_id, source_file: str):
    """
    Save extracted data to the appropriate MongoDB collection based on the schema class.
    """
    db_client = get_sync_db()
    
    # Map Extraction Schema -> DB Model
    # Since we use Base schemas for extraction, but need to save to DB collections
    if schema_class in [Form16PartA, Form16PartA_Schema]:
        collection_name = "form16_part_as"
        db_model = Form16PartA
    elif schema_class in [Form16PartB, Form16PartB_Schema]:
        collection_name = "form16_part_bs"
        db_model = Form16PartB
    elif schema_class in [AIS, AIS_Schema]:
        collection_name = "ais"
        db_model = AIS
    else:
        extraction_logger.warning(f"Unknown schema class {schema_class.__name__}, skipping DB save.")
        return

    try:
        # Instantiate model to validate and add fields
        # Note: input data is pure dict, we need to add user_id and source_file
        model_instance = db_model(
            user_id=user_id,
            source_file=Path(source_file).name,
            **data
        )
        
        # Convert back to dict for storage
        document = model_instance.model_dump(by_alias=True, exclude={"id"})
        
        # Insert
        result = db_client[collection_name].insert_one(document)
        extraction_logger.info(f"✅ Saved to DB collection '{collection_name}' with ID: {result.inserted_id}")
        return result.inserted_id

    except Exception as e:
        extraction_logger.error(f"❌ Failed to save to DB: {e}")
        # We don't raise here to avoid stopping the whole pipeline, but we log explicitly
        return None


# ============================================================
# 🚀 Extraction Pipeline (modified for local files)
# ============================================================

def process_uploaded_file(file_path: str, doc_type: str, user_id=None):
    """
    Process a single uploaded file using LlamaExtract.
    """
    extraction_logger.info(f"📄 Processing: {file_path} as {doc_type} using LlamaExtract")
    
    if not user_id:
         # Fallback for testing/manual calls
         try:
            db_client = get_sync_db()
            user_id = get_or_create_default_user(db_client)
         except Exception as e:
              extraction_logger.error(f"DB Connection failed: {e}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    schema_map = {
        "form16a": Form16PartA_Schema,
        "form16b": Form16PartB_Schema,
        "ais": AIS_Schema,
    }
    
    schema = schema_map.get(doc_type.lower())
    if not schema:
        raise ValueError(f"Unknown document type: {doc_type}")
    
    try:
        if not extractor:
             raise ValueError("LlamaExtract is not configured (API key missing).")

        agent_name = f"{Path(file_path).stem}-{uuid.uuid4().hex}"
        extraction_logger.info(f"Creating agent: {agent_name}")
        extraction_logger.info(f"Using schema: {schema.__name__}")
        
        config = ExtractConfig(invalidate_cache=True)
        agent = extractor.create_agent(name=agent_name, data_schema=schema, config=config)
        extraction_logger.info(f"Agent created, starting extraction...")
        
        result = agent.extract(file_path)
        if hasattr(result, 'data') and result.data:
            result_data = result.data
        else:
             result_data = result.data
             
        extraction_logger.info(f"Result preview: {json.dumps(result_data, indent=2, default=str)[:200]}...")
    
        # Save to JSON (Backup/Debug)
        APP_ROOT = Path(__file__).resolve().parents[1]
        output_dir = APP_ROOT / "data" / "extracted"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{Path(file_path).stem}_{timestamp}.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=4, ensure_ascii=False)
            
        # Save to DB
        db_id = save_extraction_to_db(result_data, schema, user_id, file_path)
        if db_id:
             result_data["_id"] = str(db_id)

        extraction_logger.info(f"✅ Complete → {output_path}")
        return result_data


    except Exception as e:
        extraction_logger.error(f"❌ Extraction failed: {e}")
        raise e

def extract_all_forms():
    """
    Batch process all PDF files in the input directory.
    Useful for initialization or bulk loading.
    """
    APP_ROOT = Path(__file__).resolve().parents[1]
    input_dir = APP_ROOT / "data" / "input_docs"
    
    if not input_dir.exists():
        extraction_logger.warning(f"Input directory {input_dir} does not exist. Creating...")
        input_dir.mkdir(parents=True, exist_ok=True)
        return

    # User ID Resolution (for batch process, we use default/test user)
    try:
        db_client = get_sync_db()
        user_id = get_or_create_default_user(db_client)
    except Exception as e:
        extraction_logger.error(f"Cannot get default user for batch extraction: {e}")
        return

    files = list(input_dir.glob("*.pdf"))
    if not files:
        extraction_logger.info("No PDF files found in input directory.")
        return

    extraction_logger.info(f"Found {len(files)} files to process.")
    
    for file_path in files:
        filename = file_path.name.lower()
        doc_type = None
        
        # Simple heuristic for doc type
        if "form16a" in filename or "part_a" in filename:
            doc_type = "form16a"
        elif "form16b" in filename or "part_b" in filename:
            doc_type = "form16b"
        elif "ais" in filename:
            doc_type = "ais"
            
        if doc_type:
            try:
                process_uploaded_file(str(file_path), doc_type, user_id)
            except Exception as e:
                extraction_logger.error(f"Failed to process {filename}: {e}")
        else:
            extraction_logger.warning(f"Skipping {filename}: Could not determine doc type from name.")

# ============================================================
# 🧩 Run
# ============================================================
if __name__ == "__main__":
    extract_all_forms()