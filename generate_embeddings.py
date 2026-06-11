"""
One-time script to generate bus stop embeddings and persist them to disk.

Usage:
    1. Ensure .env has LTA_ACC_KEY, LTA_ODATA_URL, and GOOGLE_API_KEY set.
    2. Run: python generate_embeddings.py
    3. The embeddings are written to ./chroma_data/ which is volume-mounted
       into the ChromaDB Docker container on startup.

Re-run this script whenever bus stop data changes (e.g. LTA adds/removes stops).
The script is resumable — it skips documents already in the collection.
"""

import os
import time
import requests
from dotenv import load_dotenv

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

CHROMA_DATA_DIR = "./chroma_data"
COLLECTION_NAME = "bus_stops"
EMBEDDING_MODEL = "models/gemini-embedding-001"
BATCH_SIZE = 25  # keep well under the 100 requests/min free-tier limit
DELAY_BETWEEN_BATCHES = 65  # seconds to wait between batches to avoid rate limits


def get_bus_stops(lta_odata_url: str, lta_acc_key: str, skip: int) -> list[dict]:
    """Fetch a page of bus stops from the LTA DataMall API."""
    url = lta_odata_url + "/BusStops"
    params = {"$skip": skip}
    headers = {"AccountKey": lta_acc_key, "accept": "application/json"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"LTA API error: status {response.status_code}")
        return []
    return response.json()["value"]


def fetch_all_bus_stops(lta_odata_url: str, lta_acc_key: str) -> list[dict]:
    """Fetch all bus stops by paginating through the LTA API."""
    all_stops = []
    skip = 0
    while True:
        page = get_bus_stops(lta_odata_url, lta_acc_key, skip)
        if not page:
            break
        all_stops.extend(page)
        skip += 500
        print(f"  Fetched {len(all_stops)} bus stops so far...")
    return all_stops


def main():
    load_dotenv()

    lta_odata_url = os.getenv("LTA_ODATA_URL")
    lta_acc_key = os.getenv("LTA_ACC_KEY")

    if not lta_odata_url or not lta_acc_key:
        raise ValueError("LTA_ODATA_URL and LTA_ACC_KEY must be set in .env")
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY must be set in .env")

    # 1. Fetch all bus stops
    print("Fetching all bus stops from LTA DataMall...")
    bus_stops = fetch_all_bus_stops(lta_odata_url, lta_acc_key)
    print(f"Total bus stops fetched: {len(bus_stops)}")

    # 2. Build LangChain documents
    documents = []
    for i, stop in enumerate(bus_stops):
        doc = Document(
            id=str(i),
            page_content=stop["Description"],
            metadata={
                "bus_stop_code": stop["BusStopCode"],
                "road_name": stop["RoadName"],
            },
        )
        documents.append(doc)

    # 3. Persist embeddings to local ChromaDB directory (written directly to disk)
    print(f"Generating embeddings with {EMBEDDING_MODEL} and persisting to {CHROMA_DATA_DIR}...")
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_DIR)

    vector_store = Chroma(
        client=chroma_client,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
    )

    # Check which documents are already in the collection (for resumability)
    collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    existing_count = collection.count()
    if existing_count > 0:
        print(f"  Found {existing_count} existing documents in collection. Resuming from where we left off...")
        documents = documents[existing_count:]
        if not documents:
            print("  All documents already embedded. Nothing to do.")
            return

    # Add documents in batches with rate limiting
    total = len(documents) + existing_count
    print(f"  {len(documents)} documents remaining to embed...")
    for start in range(0, len(documents), BATCH_SIZE):
        batch = documents[start : start + BATCH_SIZE]
        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            try:
                vector_store.add_documents(batch)
                done_count = existing_count + start + len(batch)
                print(f"  Embedded {done_count}/{total} documents")
                break
            except Exception as e:
                if "429" in str(e) or "ResourceExhausted" in str(e):
                    retry_count += 1
                    wait_time = DELAY_BETWEEN_BATCHES * retry_count
                    print(f"  Rate limited. Waiting {wait_time}s before retry {retry_count}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    raise
        else:
            print(f"  FAILED after {max_retries} retries on batch starting at {existing_count + start}. Re-run the script to resume.")
            return

        # Delay between batches to stay within rate limits
        if start + BATCH_SIZE < len(documents):
            print(f"  Waiting {DELAY_BETWEEN_BATCHES}s to respect rate limits...")
            time.sleep(DELAY_BETWEEN_BATCHES)

    print(f"\nDone! {total} embeddings persisted to {CHROMA_DATA_DIR}/")
    print("You can now start ChromaDB with docker-compose and run the app.")


if __name__ == "__main__":
    main()
